"""Orchestrator: wires agents with middleware and HITL.

This is the single entry point that CLI and server import.
It owns:
- The middleware pipeline (memory, knowledge context providers; audit, approval filters)
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


class Orchestrator:
    """Orchestrates agent execution with middleware and HITL support.

    Lifecycle of a message:
      1. before_run hooks (memory recall, knowledge retrieval)
      2. Build augmented prompt with injected context
      3. Agent generates response (may request tool calls)
      4. Tool calls run through the filter pipeline (audit, approval)
      5. after_run hooks (store memory)
      6. Response delivered to the caller
    """

    def __init__(
        self,
        *,
        approval_handler: Callable[[dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> None:
        self._settings = get_settings()
        self._memory = MemoryProvider()
        self._knowledge = KnowledgeProvider()
        self._agent = ConversationalAgent()

        # Middleware pipeline
        self._pipeline = MiddlewarePipeline(
            context_providers=[
                MemoryContextProvider(self._memory),
                KnowledgeContextProvider(self._knowledge),
            ],
            tool_filters=[
                AuditLogFilter(),
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

    async def chat(self, message: str, *, user_id: str = "default") -> str:
        """Send a message and get a response.

        Runs the full middleware pipeline: memory recall, knowledge
        retrieval, LLM generation and memory storage.
        """
        ctx = SessionContext(
            user_id=user_id,
            messages=[{"role": "user", "content": message}],
        )

        await self._pipeline.run_before(ctx)
        augmented_message = ctx.build_augmented_prompt(message)

        response = await self._agent.run(augmented_message)

        await self._pipeline.run_after(ctx, response)
        return response

    async def chat_stream(
        self, message: str, *, user_id: str = "default"
    ) -> AsyncIterator[str]:
        """Stream a response token by token.

        Same middleware pipeline as chat(), but yields tokens.
        """
        ctx = SessionContext(
            user_id=user_id,
            messages=[{"role": "user", "content": message}],
        )

        await self._pipeline.run_before(ctx)
        augmented_message = ctx.build_augmented_prompt(message)

        async for token in self._agent.run_stream(augmented_message):
            yield token

        await self._pipeline.run_after(ctx, "[streamed response]")

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
