"""Tests for the middleware pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from {{ cookiecutter.package_name }}.middleware import (
    AuditLogFilter,
    HumanApprovalFilter,
    ApprovalMode,
    KnowledgeContextProvider,
    MemoryContextProvider,
    MiddlewarePipeline,
    SessionContext,
    ToolInvocationContext,
)


class TestSessionContext:
    def test_build_augmented_prompt_no_instructions(self) -> None:
        ctx = SessionContext()
        assert ctx.build_augmented_prompt("Hello") == "Hello"

    def test_build_augmented_prompt_with_instructions(self) -> None:
        ctx = SessionContext()
        ctx.extend_instructions("memory", ["Remember: user likes coffee"])
        result = ctx.build_augmented_prompt("Hello")
        assert "Remember: user likes coffee" in result
        assert "User message: Hello" in result


class TestMemoryContextProvider:
    async def test_before_run_injects_memories(self) -> None:
        mock_memory = AsyncMock()
        mock_memory.recall.return_value = [{"content": "User bought product X"}]

        provider = MemoryContextProvider(mock_memory)
        ctx = SessionContext(
            user_id="u1",
            messages=[{"role": "user", "content": "What did I buy?"}],
        )
        await provider.before_run(ctx)

        assert len(ctx.extra_instructions) == 1
        assert "User bought product X" in ctx.extra_instructions[0]

    async def test_after_run_stores_memory(self) -> None:
        mock_memory = AsyncMock()
        provider = MemoryContextProvider(mock_memory)
        ctx = SessionContext(
            user_id="u1",
            messages=[{"role": "user", "content": "Hi"}],
        )
        await provider.after_run(ctx, "Hello there!")

        mock_memory.store.assert_called_once()
        stored = mock_memory.store.call_args[0][0]
        assert "Hi" in stored
        assert "Hello there!" in stored


class TestKnowledgeContextProvider:
    async def test_before_run_injects_knowledge(self) -> None:
        mock_knowledge = AsyncMock()
        mock_result = type("KR", (), {"content": "Product X costs $50"})()
        mock_knowledge.search.return_value = [mock_result]

        provider = KnowledgeContextProvider(mock_knowledge)
        ctx = SessionContext(
            user_id="u1",
            messages=[{"role": "user", "content": "How much is X?"}],
        )
        await provider.before_run(ctx)

        assert len(ctx.extra_instructions) == 1
        assert "Product X costs $50" in ctx.extra_instructions[0]


class TestHumanApprovalFilter:
    async def test_always_mode_requires_approval(self) -> None:
        callback = AsyncMock(return_value=True)
        f = HumanApprovalFilter(mode=ApprovalMode.ALWAYS, request_approval=callback)
        ctx = ToolInvocationContext(
            tool_name="any_tool",
            arguments={},
            session=SessionContext(),
        )
        await f.before_tool(ctx)
        assert ctx.approved is True
        callback.assert_called_once()

    async def test_never_mode_skips_approval(self) -> None:
        callback = AsyncMock(return_value=True)
        f = HumanApprovalFilter(mode=ApprovalMode.NEVER, request_approval=callback)
        ctx = ToolInvocationContext(
            tool_name="any_tool",
            arguments={},
            session=SessionContext(),
        )
        await f.before_tool(ctx)
        assert ctx.approved is True
        callback.assert_not_called()

    async def test_conditional_blocks_listed_tool(self) -> None:
        callback = AsyncMock(return_value=False)
        f = HumanApprovalFilter(
            tools_requiring_approval={"dangerous_tool"},
            request_approval=callback,
        )
        ctx = ToolInvocationContext(
            tool_name="dangerous_tool",
            arguments={"x": 1},
            session=SessionContext(),
        )
        await f.before_tool(ctx)
        assert ctx.approved is False
        assert "denied" in ctx.denial_reason.lower()

    async def test_conditional_allows_unlisted_tool(self) -> None:
        callback = AsyncMock()
        f = HumanApprovalFilter(
            tools_requiring_approval={"dangerous_tool"},
            request_approval=callback,
        )
        ctx = ToolInvocationContext(
            tool_name="safe_tool",
            arguments={},
            session=SessionContext(),
        )
        await f.before_tool(ctx)
        assert ctx.approved is True
        callback.assert_not_called()

    async def test_no_callback_blocks(self) -> None:
        f = HumanApprovalFilter(
            tools_requiring_approval={"dangerous_tool"},
            request_approval=None,
        )
        ctx = ToolInvocationContext(
            tool_name="dangerous_tool",
            arguments={},
            session=SessionContext(),
        )
        await f.before_tool(ctx)
        assert ctx.approved is False
        assert "No approval handler" in ctx.denial_reason


class TestMiddlewarePipeline:
    async def test_run_tool_approved(self) -> None:
        pipeline = MiddlewarePipeline()
        tool_fn = AsyncMock(return_value={"result": 42})
        session = SessionContext()

        ctx = await pipeline.run_tool("test_tool", {"a": 1}, session, tool_fn)

        assert ctx.approved is True
        assert ctx.result == {"result": 42}
        tool_fn.assert_called_once_with(a=1)

    async def test_run_tool_denied_by_filter(self) -> None:
        deny_filter = HumanApprovalFilter(
            mode=ApprovalMode.ALWAYS,
            request_approval=AsyncMock(return_value=False),
        )
        pipeline = MiddlewarePipeline(tool_filters=[deny_filter])
        tool_fn = AsyncMock()
        session = SessionContext()

        ctx = await pipeline.run_tool("test_tool", {}, session, tool_fn)

        assert ctx.approved is False
        tool_fn.assert_not_called()

    async def test_audit_log_filter(self) -> None:
        log_fn = AsyncMock()
        audit = AuditLogFilter(log_fn=log_fn)
        pipeline = MiddlewarePipeline(tool_filters=[audit])
        tool_fn = AsyncMock(return_value="ok")
        session = SessionContext()

        await pipeline.run_tool("my_tool", {"x": 1}, session, tool_fn)

        assert log_fn.call_count == 2  # before + after
        calls = [c[0][0] for c in log_fn.call_args_list]
        assert calls[0]["event"] == "tool_call_start"
        assert calls[1]["event"] == "tool_call_end"
