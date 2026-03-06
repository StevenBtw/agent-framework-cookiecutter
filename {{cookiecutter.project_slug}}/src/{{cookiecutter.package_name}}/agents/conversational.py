"""Conversational agent definition.

Responsible for:
- Model provider setup (Azure AI Foundry or pydantic-ai)
- Tool registry (which tools this agent can call)
- System prompt / persona

Does NOT own the middleware pipeline, memory or HITL state;
those are managed by the orchestrator.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable

{% if cookiecutter.model_provider == "azure_ai_foundry" -%}
from {{ cookiecutter.package_name }}.providers.model import create_azure_openai_client
{%- elif cookiecutter.model_provider == "pydantic_ai_custom" -%}
from {{ cookiecutter.package_name }}.providers.model import create_pydantic_agent
{%- endif %}
from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.tools import (
    trigger_async_operation,
    send_quote_for_approval,
    request_document_generation,
    get_entity,
    create_entity,
    update_entity,
    update_preferences,
    execute_logic,
    calculate_quotation,
    fuzzy_search,
)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Callable[..., Awaitable[Any]]] = {
    # Async (fire-and-forget)
    "trigger_async_operation": trigger_async_operation,
    "send_quote_for_approval": send_quote_for_approval,
    "request_document_generation": request_document_generation,
    # Data (synchronous CRUD)
    "get_entity": get_entity,
    "create_entity": create_entity,
    "update_entity": update_entity,
    "update_preferences": update_preferences,
    # Logic (synchronous computation)
    "execute_logic": execute_logic,
    "calculate_quotation": calculate_quotation,
    "fuzzy_search": fuzzy_search,
}


class ConversationalAgent:
    """A single conversational agent with its model and tools.

    This class is intentionally focused: it knows how to talk to an LLM
    and which tools are available.  Context injection (memory, knowledge)
    and policy enforcement (HITL, audit) live in the orchestrator.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._setup_model()

    @property
    def name(self) -> str:
        return self._settings.agent_name

    @property
    def instructions(self) -> str:
        return self._settings.agent_instructions

    @property
    def tools(self) -> dict[str, Callable[..., Awaitable[Any]]]:
        return TOOL_REGISTRY

    def _setup_model(self) -> None:
        {% if cookiecutter.model_provider == "azure_ai_foundry" -%}
        self._client = create_azure_openai_client()
        {%- elif cookiecutter.model_provider == "pydantic_ai_custom" -%}
        self._agent = create_pydantic_agent(self._settings.agent_instructions)
        {%- endif %}

    async def run(self, messages: list[dict[str, Any]]) -> str:
        """Send messages to the LLM and return the full response.

        Args:
            messages: Conversation history as a list of
                ``{"role": "...", "content": "..."}`` dicts.
        """
        {% if cookiecutter.model_provider == "azure_ai_foundry" -%}
        response = await self._client.responses.create(
            model=self._settings.azure_openai_deployment,
            input=messages,
            instructions=self.instructions,
        )
        return response.output_text
        {%- elif cookiecutter.model_provider == "pydantic_ai_custom" -%}
        # pydantic-ai takes the latest user message as the prompt
        # and prior turns as message_history.
        prompt = messages[-1]["content"] if messages else ""
        history = messages[:-1] if len(messages) > 1 else []
        result = await self._agent.run(prompt, message_history=history)
        return result.output
        {%- endif %}

    async def run_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Stream tokens from the LLM.

        Args:
            messages: Conversation history as a list of
                ``{"role": "...", "content": "..."}`` dicts.
        """
        {% if cookiecutter.model_provider == "azure_ai_foundry" -%}
        stream = await self._client.responses.create(
            model=self._settings.azure_openai_deployment,
            input=messages,
            instructions=self.instructions,
            stream=True,
        )
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
        {%- elif cookiecutter.model_provider == "pydantic_ai_custom" -%}
        prompt = messages[-1]["content"] if messages else ""
        history = messages[:-1] if len(messages) > 1 else []
        async with self._agent.run_stream(prompt, message_history=history) as result:
            async for token in result.stream_text():
                yield token
        {%- endif %}
