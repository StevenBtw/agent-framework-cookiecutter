"""Tests for the orchestrator and agent integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator


class TestOrchestrator:
    """Tests for the Orchestrator."""

    async def test_chat_runs_middleware_and_agent(self, mock_orchestrator: Orchestrator) -> None:
        """Orchestrator should run middleware hooks and call the agent."""
        response = await mock_orchestrator.chat("Hi there", user_id="test-user")

        assert response == "Hello!"
        mock_orchestrator._agent.run.assert_called_once()

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
