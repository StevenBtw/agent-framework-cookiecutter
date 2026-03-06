"""Middleware pipeline inspired by Microsoft Agent Framework.

Implements the context-provider / hooks pattern from the framework's Python SDK:
- ContextProvider: before_run / after_run hooks for injecting context
- ToolFilter: before_tool / after_tool hooks for intercepting tool calls
- HumanApprovalFilter: requires human approval before executing sensitive tools

The pipeline runs linearly (not onion-style):
  1. All before_run() hooks in order
  2. Agent invocation
  3. All after_run() hooks in reverse order

For tool calls:
  1. All before_tool() hooks in order  (can block execution)
  2. Tool execution
  3. All after_tool() hooks in reverse order
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """Per-invocation state that context providers read and write."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default"
    messages: list[dict[str, Any]] = field(default_factory=list)
    extra_instructions: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def extend_messages(self, source_id: str, messages: list[dict[str, Any]]) -> None:
        for msg in messages:
            self.messages.append({**msg, "_source": source_id})

    def extend_instructions(self, source_id: str, instructions: list[str]) -> None:
        for inst in instructions:
            self.extra_instructions.append(inst)
        self.state.setdefault("_instruction_sources", []).append(source_id)

    def build_augmented_messages(
        self,
        history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build a full message list for the LLM.

        Returns a list starting with a system message (if there are
        extra instructions), followed by conversation history, followed
        by the current user message(s) from ``self.messages``.
        """
        result: list[dict[str, Any]] = []

        if self.extra_instructions:
            result.append({
                "role": "system",
                "content": "\n\n".join(self.extra_instructions),
            })

        if history:
            result.extend(history)

        result.extend(self.messages)
        return result

    def build_augmented_prompt(self, user_message: str) -> str:
        """Combine extra instructions with the user message.

        Kept for backward compatibility; prefer :meth:`build_augmented_messages`.
        """
        if not self.extra_instructions:
            return user_message
        context = "\n\n".join(self.extra_instructions)
        return f"{context}\n\nUser message: {user_message}"


# ---------------------------------------------------------------------------
# Context providers (before_run / after_run)
# ---------------------------------------------------------------------------

class ContextProvider:
    """Base class for context providers.

    Subclass and override before_run / after_run to inject memories,
    knowledge, or other context into the session.
    """

    source_id: str = "base"

    async def before_run(self, context: SessionContext) -> None:
        """Called before the agent processes a message."""

    async def after_run(self, context: SessionContext, response: str) -> None:
        """Called after the agent produces a response."""


class MemoryContextProvider(ContextProvider):
    """Injects relevant memories into the session context."""

    source_id = "memory"

    def __init__(self, memory_provider: Any) -> None:
        self._memory = memory_provider

    async def before_run(self, context: SessionContext) -> None:
        user_msg = next(
            (m["content"] for m in reversed(context.messages) if m.get("role") == "user"),
            "",
        )
        if not user_msg:
            return
        memories = await self._memory.recall(user_msg, user_id=context.user_id, limit=5)
        if memories:
            memory_text = "\n".join(
                m.get("content", m.get("memory", "")) for m in memories
            )
            context.extend_instructions(self.source_id, [
                f"Relevant memories for this user:\n{memory_text}",
            ])

    async def after_run(self, context: SessionContext, response: str) -> None:
        user_msg = next(
            (m["content"] for m in reversed(context.messages) if m.get("role") == "user"),
            "",
        )
        if user_msg:
            await self._memory.store(
                f"User: {user_msg}\nAssistant: {response}",
                user_id=context.user_id,
            )


class KnowledgeContextProvider(ContextProvider):
    """Injects relevant knowledge/RAG results into the session context."""

    source_id = "knowledge"

    def __init__(self, knowledge_provider: Any) -> None:
        self._knowledge = knowledge_provider

    async def before_run(self, context: SessionContext) -> None:
        user_msg = next(
            (m["content"] for m in reversed(context.messages) if m.get("role") == "user"),
            "",
        )
        if not user_msg:
            return
        results = await self._knowledge.search(user_msg, top_k=3)
        if results:
            knowledge_text = "\n".join(r.content for r in results)
            context.extend_instructions(self.source_id, [
                f"Relevant knowledge:\n{knowledge_text}",
            ])


# ---------------------------------------------------------------------------
# Tool filter (before_tool / after_tool)
# ---------------------------------------------------------------------------

@dataclass
class ToolInvocationContext:
    """Context for a tool invocation intercepted by filters."""

    tool_name: str
    arguments: dict[str, Any]
    session: SessionContext
    result: Any = None
    approved: bool = True
    denial_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolFilter:
    """Base class for tool invocation filters."""

    async def before_tool(self, context: ToolInvocationContext) -> None:
        """Called before a tool executes. Set context.approved = False to block."""

    async def after_tool(self, context: ToolInvocationContext) -> None:
        """Called after a tool executes. Can inspect/modify context.result."""


# ---------------------------------------------------------------------------
# Human-in-the-loop approval filter
# ---------------------------------------------------------------------------

class ApprovalMode(enum.Enum):
    ALWAYS = "always"
    NEVER = "never"
    CONDITIONAL = "conditional"


class HumanApprovalFilter(ToolFilter):
    """Requires human operator approval before executing sensitive tools.

    When approval is needed, calls ``request_approval`` with a request dict
    and awaits a boolean response.  The callback is typically wired to
    the operator WebSocket so a human can approve/deny in real time.

    Example:
        filter = HumanApprovalFilter(
            tools_requiring_approval={"send_quote_for_approval", "update_preferences"},
            request_approval=my_ws_approval_callback,
        )
    """

    def __init__(
        self,
        *,
        tools_requiring_approval: set[str] | None = None,
        mode: ApprovalMode = ApprovalMode.CONDITIONAL,
        request_approval: Callable[[dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> None:
        self._tools = tools_requiring_approval or set()
        self._mode = mode
        self._request_approval = request_approval

    def _needs_approval(self, tool_name: str) -> bool:
        if self._mode == ApprovalMode.ALWAYS:
            return True
        if self._mode == ApprovalMode.NEVER:
            return False
        return tool_name in self._tools

    async def before_tool(self, context: ToolInvocationContext) -> None:
        if not self._needs_approval(context.tool_name):
            return

        if self._request_approval is None:
            context.approved = False
            context.denial_reason = "No approval handler configured"
            return

        request = {
            "type": "approval_request",
            "request_id": str(uuid.uuid4()),
            "tool_name": context.tool_name,
            "arguments": context.arguments,
            "session_id": context.session.session_id,
            "user_id": context.session.user_id,
        }
        context.approved = await self._request_approval(request)
        if not context.approved:
            context.denial_reason = "Operator denied the action"


class AuditLogFilter(ToolFilter):
    """Logs every tool invocation for compliance / audit trail."""

    def __init__(self, log_fn: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        self._log_fn = log_fn

    async def _log(self, entry: dict[str, Any]) -> None:
        if self._log_fn:
            await self._log_fn(entry)

    async def before_tool(self, context: ToolInvocationContext) -> None:
        await self._log({
            "event": "tool_call_start",
            "tool": context.tool_name,
            "args": context.arguments,
            "session_id": context.session.session_id,
        })

    async def after_tool(self, context: ToolInvocationContext) -> None:
        await self._log({
            "event": "tool_call_end",
            "tool": context.tool_name,
            "approved": context.approved,
            "session_id": context.session.session_id,
        })


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class MiddlewarePipeline:
    """Orchestrates context providers and tool filters.

    Example::

        pipeline = MiddlewarePipeline(
            context_providers=[
                MemoryContextProvider(memory),
                KnowledgeContextProvider(knowledge),
            ],
            tool_filters=[
                AuditLogFilter(log_fn=...),
                HumanApprovalFilter(tools_requiring_approval={"send_quote_for_approval"}),
            ],
        )

        ctx = SessionContext(user_id="u1", messages=[{"role": "user", "content": "Hi"}])
        await pipeline.run_before(ctx)
        prompt = ctx.build_augmented_prompt(original_message)
        response = await agent.run(prompt)
        await pipeline.run_after(ctx, response)
    """

    def __init__(
        self,
        *,
        context_providers: list[ContextProvider] | None = None,
        tool_filters: list[ToolFilter] | None = None,
    ) -> None:
        self._context_providers = context_providers or []
        self._tool_filters = tool_filters or []

    async def run_before(self, context: SessionContext) -> None:
        for provider in self._context_providers:
            await provider.before_run(context)

    async def run_after(self, context: SessionContext, response: str) -> None:
        for provider in reversed(self._context_providers):
            await provider.after_run(context, response)

    async def run_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session: SessionContext,
        tool_fn: Callable[..., Awaitable[Any]],
    ) -> ToolInvocationContext:
        """Execute a tool through the filter pipeline.

        Returns the ToolInvocationContext so callers can inspect
        ``ctx.approved``, ``ctx.result``, and ``ctx.denial_reason``.
        """
        ctx = ToolInvocationContext(
            tool_name=tool_name,
            arguments=arguments,
            session=session,
        )

        for f in self._tool_filters:
            await f.before_tool(ctx)
            if not ctx.approved:
                break

        if ctx.approved:
            ctx.result = await tool_fn(**arguments)

        for f in reversed(self._tool_filters):
            await f.after_tool(ctx)

        return ctx
