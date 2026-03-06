"""Tests for the orchestrator and agent integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator


class TestOrchestrator:
    """Tests for the Orchestrator."""

    async def test_chat_runs_middleware_and_agent(self, mock_orchestrator: Orchestrator) -> None:
        """Orchestrator should run middleware hooks and call the agent."""
        response = await mock_orchestrator.chat(
            "Hi there", user_id="test-user", session_id="s1",
        )

        assert response == "Hello!"
        mock_orchestrator._agent.run.assert_called_once()
        # Agent should receive a message list, not a string
        call_args = mock_orchestrator._agent.run.call_args[0][0]
        assert isinstance(call_args, list)
        assert any(m["content"] == "Hi there" for m in call_args)

    async def test_chat_stores_history(self, mock_orchestrator: Orchestrator) -> None:
        """Orchestrator should store conversation turns in history."""
        await mock_orchestrator.chat("Hello", user_id="u1", session_id="s1")
        history = mock_orchestrator._history.get("u1", "s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    async def test_chat_passes_history_to_agent(self, mock_orchestrator: Orchestrator) -> None:
        """Second message should include history from the first turn."""
        await mock_orchestrator.chat("First", user_id="u1", session_id="s1")
        await mock_orchestrator.chat("Second", user_id="u1", session_id="s1")

        # The second call should include history from the first turn
        second_call = mock_orchestrator._agent.run.call_args_list[1][0][0]
        contents = [m["content"] for m in second_call]
        assert "First" in contents
        assert "Hello!" in contents  # assistant response from first turn
        assert "Second" in contents

    async def test_handoff_state(self, mock_orchestrator: Orchestrator) -> None:
        """Orchestrator tracks HITL handoff state per session."""
        assert not mock_orchestrator.is_handed_off("s1")

        mock_orchestrator.hand_off("s1")
        assert mock_orchestrator.is_handed_off("s1")
        assert not mock_orchestrator.is_handed_off("s2")

        mock_orchestrator.resume("s1")
        assert not mock_orchestrator.is_handed_off("s1")

    async def test_execute_tool_unknown(self, mock_orchestrator: Orchestrator) -> None:
        """Executing an unknown tool returns a denial."""
        result = await mock_orchestrator.execute_tool("nonexistent_tool", {})
        assert result["approved"] is False
        assert "Unknown tool" in result["denial_reason"]
