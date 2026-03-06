"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator
from {{ cookiecutter.package_name }}.middleware import (
    MiddlewarePipeline,
    SessionContext,
)
from {{ cookiecutter.package_name }}.utils.history import ConversationHistory


@pytest.fixture
def mock_orchestrator() -> Orchestrator:
    """Create an Orchestrator with mocked dependencies."""
    mock_memory = AsyncMock()
    mock_memory.recall.return_value = []
    mock_memory.store.return_value = "memory-id"
    mock_memory.get_all.return_value = []

    mock_knowledge = AsyncMock()
    mock_knowledge.search.return_value = []

    mock_agent = AsyncMock()
    mock_agent.name = "test-agent"
    mock_agent.instructions = "You are a test assistant."
    mock_agent.tools = {}
    mock_agent.run = AsyncMock(return_value="Hello!")

    orch = object.__new__(Orchestrator)
    orch._settings = type("Settings", (), {
        "agent_name": "test-agent",
        "agent_instructions": "You are a test assistant.",
        "hitl_tools_requiring_approval": "",
        "max_turns": 40,
    })()
    orch._memory = mock_memory
    orch._knowledge = mock_knowledge
    orch._agent = mock_agent
    orch._pipeline = MiddlewarePipeline()
    orch._history = ConversationHistory(max_turns=40)
    orch._handed_off = {}

    return orch


@pytest.fixture
def sample_entity() -> dict[str, Any]:
    """Sample entity for data service tests."""
    return {
        "id": "123",
        "name": "Test Entity",
        "type": "customer",
        "attributes": {"email": "test@example.com"},
    }


@pytest.fixture
def session_context() -> SessionContext:
    """A fresh session context for middleware tests."""
    return SessionContext(
        user_id="test-user",
        messages=[{"role": "user", "content": "Hello"}],
    )
