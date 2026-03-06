"""Model provider configuration."""

from __future__ import annotations

{% if cookiecutter.model_provider == "azure_ai_foundry" -%}
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from {{ cookiecutter.package_name }}.config import get_settings


def create_azure_openai_client() -> AsyncAzureOpenAI:
    """Create an async Azure OpenAI client using Entra ID credentials.

    Uses ``DefaultAzureCredential`` for token-based auth against the
    Azure OpenAI endpoint.  The returned client exposes the OpenAI
    Responses API (``client.responses.create``).
    """
    settings = get_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )

{%- elif cookiecutter.model_provider == "pydantic_ai_custom" -%}
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from {{ cookiecutter.package_name }}.config import get_settings


def create_pydantic_model() -> OpenAIChatModel:
    """Create a custom model provider via pydantic-ai.

    Supports any OpenAI-compatible API endpoint.
    """
    settings = get_settings()
    return OpenAIChatModel(
        settings.custom_model_name,
        provider=OpenAIProvider(
            base_url=settings.custom_model_base_url,
            api_key=settings.custom_model_api_key,
        ),
    )


def create_pydantic_agent(system_prompt: str | None = None) -> PydanticAgent:
    """Create a pydantic-ai agent with the custom model."""
    settings = get_settings()
    model = create_pydantic_model()
    return PydanticAgent(
        model,
        system_prompt=system_prompt or settings.agent_instructions,
    )
{%- endif %}
