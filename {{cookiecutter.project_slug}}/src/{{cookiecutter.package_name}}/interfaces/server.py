{%- if cookiecutter.interface in ["fastapi", "both"] -%}
"""FastAPI server with customer WebSocket, operator WebSocket and inbound webhooks.

WebSocket protocol (customer  ``/ws/chat``):
  Client sends:  {"type": "message",  "message": "...", "user_id": "..."}
  Server sends:  {"type": "token",    "data": "..."}           -- streaming token
                  {"type": "done"}                               -- response complete
                  {"type": "error",    "data": "..."}           -- error occurred
                  {"type": "transferred_to_human"}               -- HITL: full handoff
                  {"type": "human_message",    "data": "..."}   -- HITL: message from operator
                  {"type": "agent_resumed"}                      -- HITL: AI agent takes back
                  {"type": "approval_pending", "request": {...}} -- HITL: waiting for operator
                  {"type": "approval_result",  "approved": bool} -- HITL: operator decided
                  {"type": "async_result",     "data": {...}}   -- async op completed (webhook)

WebSocket protocol (operator  ``/ws/operator``):
  Server sends:  {"type": "approval_request", ...}              -- tool needs approval
                  {"type": "conversation_update", ...}           -- live transcript
                  {"type": "handoff_request", ...}               -- agent requests human takeover
  Client sends:  {"type": "approval_response", "request_id": "...", "approved": bool}
                  {"type": "operator_message",  "session_id": "...", "message": "..."}
                  {"type": "resume_agent",      "session_id": "..."}
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import Depends, FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from {{ cookiecutter.package_name }}.auth import UserIdentity, resolve_identity
from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.orchestrator import Orchestrator
from {{ cookiecutter.package_name }}.utils.errors import AgentError, format_error_response
from {{ cookiecutter.package_name }}.utils.logging import get_logger, setup_logging
from {{ cookiecutter.package_name }}.utils.rate_limiting import TokenBucket, rate_limit_dependency
from {{ cookiecutter.package_name }}.utils.schemas import (
    AsyncResultPayload,
    ChatRequest,
    ChatResponse,
)
from {{ cookiecutter.package_name }}.utils.tracing import (
    get_request_id,
    trace_request,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

orchestrator: Orchestrator
rate_limiter: TokenBucket

# session_id -> customer WebSocket
customer_connections: dict[str, WebSocket] = {}

# operator WebSockets (multiple operators can connect)
operator_connections: list[WebSocket] = []

# pending approval futures: request_id -> asyncio.Future[bool]
pending_approvals: dict[str, asyncio.Future[bool]] = {}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global orchestrator, rate_limiter
    settings = get_settings()
    setup_logging(json_output=settings.log_json, level=settings.log_level)
    orchestrator = Orchestrator(approval_handler=request_operator_approval)
    rate_limiter = TokenBucket(
        rate=settings.rate_limit_rpm / 60.0,
        capacity=settings.rate_limit_burst,
    )
    yield


app = FastAPI(
    title="{{ cookiecutter.project_name }}",
    description="{{ cookiecutter.description }}",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Tracing middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def tracing_middleware(request: Request, call_next: Any) -> Response:
    """Set request/correlation IDs and add them to the response headers."""
    correlation_id = request.headers.get("x-correlation-id")
    with trace_request(correlation_id=correlation_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = get_request_id()
        return response


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

@app.exception_handler(AgentError)
async def agent_error_handler(request: Request, exc: AgentError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc),
        headers={"X-Request-ID": get_request_id()},
    )


# ---------------------------------------------------------------------------
# Rate limiting dependency
# ---------------------------------------------------------------------------

async def _require_rate_limit(request: Request) -> None:
    checker = rate_limit_dependency(rate_limiter)
    await checker(request)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/chat", dependencies=[Depends(_require_rate_limit)])
async def chat(
    request: ChatRequest,
    identity: UserIdentity = Depends(resolve_identity),
) -> ChatResponse:
    """Non-streaming chat endpoint.

    User identity is resolved from the Authorization header (JWT).
    If the request body includes ``user_id`` it is used as a fallback
    for unauthenticated callers (e.g. ``prospect:abc123``).
    """
    user_id = identity.user_id if identity.authenticated else (request.user_id or identity.user_id)
    session_id = request.session_id or user_id
    response = await orchestrator.chat(request.message, user_id=user_id, session_id=session_id)
    return ChatResponse(response=response, session_id=session_id)


@app.post("/chat/stream", dependencies=[Depends(_require_rate_limit)])
async def chat_stream(
    request: ChatRequest,
    identity: UserIdentity = Depends(resolve_identity),
) -> StreamingResponse:
    """Streaming chat endpoint using Server-Sent Events."""
    user_id = identity.user_id if identity.authenticated else (request.user_id or identity.user_id)
    session_id = request.session_id or user_id

    async def event_generator() -> AsyncIterator[str]:
        async for token in orchestrator.chat_stream(request.message, user_id=user_id, session_id=session_id):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Inbound webhook: async operation results
# ---------------------------------------------------------------------------

@app.post("/webhooks/async-result")
async def async_result_webhook(payload: AsyncResultPayload) -> dict[str, str]:
    """Receive a callback when an async operation completes.

    The external system (quote engine, document generator, etc.) posts
    here with the correlation_id and result.  We push it to the
    customer's WebSocket so they see the update in real time.
    """
    ws = customer_connections.get(payload.session_id)
    if ws:
        await ws.send_json({
            "type": "async_result",
            "data": {
                "correlation_id": payload.correlation_id,
                "status": payload.status,
                **payload.data,
            },
        })
    await _broadcast_to_operators({
        "type": "async_result",
        "session_id": payload.session_id,
        "correlation_id": payload.correlation_id,
        "status": payload.status,
        "data": payload.data,
    })
    return {"status": "received"}


# ---------------------------------------------------------------------------
# Customer WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """Full-duplex WebSocket for the customer-facing chat UI.

    Supports streaming AI responses plus HITL events
    (transfer, operator messages, approval status).
    """
    await websocket.accept()
    session_id: str | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                message = data.get("message", "")
                user_id = data.get("user_id", "default")
                session_id = data.get("session_id", user_id)

                customer_connections[session_id] = websocket

                if not message:
                    await websocket.send_json({"type": "error", "data": "Empty message"})
                    continue

                await _broadcast_to_operators({
                    "type": "conversation_update",
                    "session_id": session_id,
                    "role": "customer",
                    "message": message,
                })

                if orchestrator.is_handed_off(session_id):
                    await _broadcast_to_operators({
                        "type": "handoff_message",
                        "session_id": session_id,
                        "message": message,
                    })
                    continue

                with trace_request():
                    try:
                        chunks: list[str] = []
                        async for token in orchestrator.chat_stream(
                            message, user_id=user_id, session_id=session_id,
                        ):
                            chunks.append(token)
                            await websocket.send_json({"type": "token", "data": token})
                        await websocket.send_json({"type": "done"})

                        await _broadcast_to_operators({
                            "type": "conversation_update",
                            "session_id": session_id,
                            "role": "agent",
                            "message": "".join(chunks),
                        })
                    except AgentError as e:
                        logger.warning("agent error in ws", extra={"session_id": session_id})
                        await websocket.send_json({"type": "error", "data": e.message})
                    except Exception as e:
                        logger.exception("unexpected error in ws", extra={"session_id": session_id})
                        await websocket.send_json({"type": "error", "data": str(e)})

    except WebSocketDisconnect:
        if session_id:
            customer_connections.pop(session_id, None)


# ---------------------------------------------------------------------------
# Operator WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/operator")
async def websocket_operator(websocket: WebSocket) -> None:
    """WebSocket for human operators.

    Operators receive live conversation updates, approval requests and
    handoff requests.  They can approve/deny tool calls, send messages
    directly to customers or resume the AI agent.
    """
    await websocket.accept()
    operator_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "approval_response":
                request_id = data.get("request_id", "")
                approved = data.get("approved", False)
                future = pending_approvals.pop(request_id, None)
                if future and not future.done():
                    future.set_result(approved)

                session_id = data.get("session_id", "")
                ws = customer_connections.get(session_id)
                if ws:
                    await ws.send_json({
                        "type": "approval_result",
                        "approved": approved,
                    })

            elif msg_type == "operator_message":
                session_id = data.get("session_id", "")
                message = data.get("message", "")
                ws = customer_connections.get(session_id)
                if ws:
                    await ws.send_json({
                        "type": "human_message",
                        "data": message,
                    })

            elif msg_type == "takeover":
                session_id = data.get("session_id", "")
                orchestrator.hand_off(session_id)
                ws = customer_connections.get(session_id)
                if ws:
                    await ws.send_json({"type": "transferred_to_human"})

            elif msg_type == "resume_agent":
                session_id = data.get("session_id", "")
                orchestrator.resume(session_id)
                ws = customer_connections.get(session_id)
                if ws:
                    await ws.send_json({"type": "agent_resumed"})

    except WebSocketDisconnect:
        operator_connections.remove(websocket)


# ---------------------------------------------------------------------------
# Approval callback (wired into HumanApprovalFilter)
# ---------------------------------------------------------------------------

async def request_operator_approval(request: dict[str, Any]) -> bool:
    """Send an approval request to all connected operators and wait.

    This function is passed as the ``request_approval`` callback to
    ``HumanApprovalFilter`` in the middleware pipeline.  It broadcasts
    the request to operator WebSockets and blocks until one responds.
    """
    request_id = request["request_id"]
    loop = asyncio.get_event_loop()
    future: asyncio.Future[bool] = loop.create_future()
    pending_approvals[request_id] = future

    session_id = request.get("session_id", "")
    ws = customer_connections.get(session_id)
    if ws:
        await ws.send_json({
            "type": "approval_pending",
            "request": {
                "tool_name": request.get("tool_name"),
                "request_id": request_id,
            },
        })

    await _broadcast_to_operators(request)

    try:
        return await asyncio.wait_for(future, timeout=300.0)
    except asyncio.TimeoutError:
        pending_approvals.pop(request_id, None)
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _broadcast_to_operators(message: dict[str, Any]) -> None:
    """Send a JSON message to all connected operator WebSockets."""
    disconnected: list[WebSocket] = []
    for ws in operator_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        operator_connections.remove(ws)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    """Entry point for the server."""
    uvicorn.run(
        "{{ cookiecutter.package_name }}.interfaces.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
{%- endif %}
