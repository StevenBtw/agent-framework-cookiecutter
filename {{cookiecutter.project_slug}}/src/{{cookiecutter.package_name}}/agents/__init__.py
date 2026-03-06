"""Agent definitions.

Each module in this package defines an agent: its model provider,
tool registry and system prompt.  The orchestrator imports agents
and wraps them with middleware (memory, knowledge, HITL).
"""

from {{ cookiecutter.package_name }}.agents.conversational import ConversationalAgent

__all__ = ["ConversationalAgent"]
