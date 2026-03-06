"""Orchestrator: wires agents with middleware and HITL.

This is the single entry point that CLI and server import.
It owns:
- The middleware pipeline (memory, knowledge context providers; audit, approval filters)
- Conversation history (per-session message lists)
- HITL handoff state
- Tool execution through the filter pipeline

It delegates actual LLM calls to agents defined in the ``agents`` package.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable

from {{ cookiecutter.package_name }}.agents import ConversationalAgent
from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.memory.provider import MemoryProvider
from {{ cookiecutter.package_name }}.knowledge.provider import KnowledgeProvider
from {{ cookiecutter.package_name }}.middleware import (
    AuditLogFilter,
    HumanApprovalFilter,
    KnowledgeContextProvider,
    MemoryContextProvider,
    MiddlewarePipeline,
    SessionContext,
)
from {{ cookiecutter.package_name }}.utils.history import ConversationHistory
from {{ cookiecutter.package_name }}.utils.logging import audit_log_fn, get_logger, setup_logging

logger = get_logger(__name__)


class Orchestrator:
    """Orchestrates agent execution with middleware and HITL support.

    Lifecycle of a message:
      1. Load conversation history for the session
      2. before_run hooks (memory recall, knowledge retrieval)
      3. Build augmented message list with injected context
      4. Agent generates response (may request tool calls)
      5. Tool calls run through the filter pipeline (audit, approval)
      6. after_run hooks (store memory)
      7. Append turn to conversation history
      8. Response delivered to the caller
    """

    def __init__(
        self,
        *,
        approval_handler: Callable[[dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> None:
        self._settings = get_settings()

        # Logging
        setup_logging(
            json_output=self._settings.log_json,
            level=self._settings.log_level,
        )

        self._memory = MemoryProvider()
        self._knowledge = KnowledgeProvider()
        self._agent = ConversationalAgent()
        self._history = ConversationHistory(max_turns=self._settings.max_turns)

        # Middleware pipeline
        self._pipeline = MiddlewarePipeline(
            context_providers=[
                MemoryContextProvider(self._memory),
                KnowledgeContextProvider(self._knowledge),
            ],
            tool_filters=[
                AuditLogFilter(log_fn=audit_log_fn),
                HumanApprovalFilter(
                    tools_requiring_approval=set(
                        self._settings.hitl_tools_requiring_approval.split(",")
                    ),
                    request_approval=approval_handler,
                ),
            ],
        )

        # HITL handoff state: session_id -> True means human has taken over
        self._handed_off: dict[str, bool] = {}

    @property
    def agent(self) -> ConversationalAgent:
        return self._agent

    # ------------------------------------------------------------------
    # HITL handoff state
    # ------------------------------------------------------------------

    def is_handed_off(self, session_id: str) -> bool:
        """Check if a session is currently handled by a human operator."""
        return self._handed_off.get(session_id, False)

    def hand_off(self, session_id: str) -> None:
        """Transfer a session to a human operator."""
        self._handed_off[session_id] = True

    def resume(self, session_id: str) -> None:
        """Hand a session back to the AI agent."""
        self._handed_off.pop(session_id, None)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
    ) -> str:
        """Send a message and get a response.

        Runs the full middleware pipeline: history, memory recall,
        knowledge retrieval, LLM generation and memory storage.
        """
        history = self._history.get(user_id, session_id)

        ctx = SessionContext(
            session_id=session_id,
            user_id=user_id,
            messages=[{"role": "user", "content": message}],
        )

        await self._pipeline.run_before(ctx)
        augmented = ctx.build_augmented_messages(history)

        logger.debug("agent.run", extra={"user_id": user_id, "session_id": session_id})
        response = await self._agent.run(augmented)

        await self._pipeline.run_after(ctx, response)

        self._history.add(user_id, session_id, "user", message)
        self._history.add(user_id, session_id, "assistant", response)

        return response

    async def chat_stream(
        self,
        message: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
    ) -> AsyncIterator[str]:
        """Stream a response token by token.

        Same middleware pipeline as chat(), but yields tokens and
        captures the full response for memory storage and history.
        """
        history = self._history.get(user_id, session_id)

        ctx = SessionContext(
            session_id=session_id,
            user_id=user_id,
            messages=[{"role": "user", "content": message}],
        )

        await self._pipeline.run_before(ctx)
        augmented = ctx.build_augmented_messages(history)

        logger.debug("agent.run_stream", extra={"user_id": user_id, "session_id": session_id})

        chunks: list[str] = []
        async for token in self._agent.run_stream(augmented):
            chunks.append(token)
            yield token

        full_response = "".join(chunks)
        await self._pipeline.run_after(ctx, full_response)

        self._history.add(user_id, session_id, "user", message)
        self._history.add(user_id, session_id, "assistant", full_response)

    # ------------------------------------------------------------------
    # Tool execution (through filter pipeline)
    # ------------------------------------------------------------------

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user_id: str = "default",
    ) -> dict[str, Any]:
        """Execute a registered tool through the middleware filter pipeline.

        Returns a dict with ``approved``, ``result`` and optionally
        ``denial_reason`` if the tool was blocked.
        """
        tool_fn = self._agent.tools.get(tool_name)
        if tool_fn is None:
            return {"approved": False, "denial_reason": f"Unknown tool: {tool_name}"}

        session = SessionContext(user_id=user_id)
        ctx = await self._pipeline.run_tool(
            tool_name=tool_name,
            arguments=arguments,
            session=session,
            tool_fn=tool_fn,
        )

        if not ctx.approved:
            return {"approved": False, "denial_reason": ctx.denial_reason}

        return {"approved": True, "result": ctx.result}
