"""Data service tools for synchronous CRUD operations.

For real-time GET/POST/PUT against a data API that returns immediately.

Real-world examples:
- Update a customer's communication preferences
- Store or retrieve contact details
- Toggle feature flags for an account
- Save a draft order
"""

from __future__ import annotations

from typing import Any

from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.tools.base import ServiceClient


def _get_client() -> ServiceClient:
    settings = get_settings()
    return ServiceClient(
        base_url=settings.data_service.base_url,
        timeout=settings.data_service.timeout,
{%- if cookiecutter.auth_method == "bearer_token" %}
        api_key=settings.data_service.api_key,
{%- endif %}
    )


async def get_entity(
    entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    """Retrieve an entity by type and ID.

    Args:
        entity_type: The entity type/resource path (e.g. "customers", "products").
        entity_id: The entity identifier.

    Returns:
        The entity data as a dict.
    """
    client = _get_client()
    try:
        response = await client.get(f"/{entity_type}/{entity_id}")
        return response.json()
    finally:
        await client.close()


async def create_entity(
    entity_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Create a new entity.

    Args:
        entity_type: The entity type/resource path.
        data: The entity data.

    Returns:
        The created entity data (including generated ID).
    """
    client = _get_client()
    try:
        response = await client.post(f"/{entity_type}", json=data)
        return response.json()
    finally:
        await client.close()


async def update_entity(
    entity_type: str,
    entity_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Update an existing entity.

    Args:
        entity_type: The entity type/resource path.
        entity_id: The entity identifier.
        data: The updated entity data.

    Returns:
        The updated entity data.
    """
    client = _get_client()
    try:
        response = await client.put(f"/{entity_type}/{entity_id}", json=data)
        return response.json()
    finally:
        await client.close()


async def update_preferences(
    customer_id: str,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """Update a customer's communication / notification preferences.

    The agent calls this when a customer says things like
    "Don't email me, I prefer SMS" or "Switch me to monthly billing".

    Args:
        customer_id: The customer identifier.
        preferences: Key-value pairs to update, e.g.:
            - channel (str): "email" | "sms" | "push" | "whatsapp"
            - frequency (str): "immediate" | "daily_digest" | "weekly"
            - language (str): ISO 639-1 code
            - opt_out_marketing (bool)

    Returns:
        The updated preferences record.
    """
    return await update_entity(
        "customers",
        f"{customer_id}/preferences",
        preferences,
    )
