"""Async (fire-and-forget) API tools.

For triggering long-running operations that return HTTP 201/202 Accepted.
The result arrives later via an inbound webhook (see ``server.py``
``POST /webhooks/async-result``).

Real-world examples:
- Send a quote for customer approval
- Request a document to be generated and signed
- Trigger an order-fulfilment workflow
- Submit a background check or compliance review
"""

from __future__ import annotations

from typing import Any

from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.tools.base import ServiceClient


def _get_client() -> ServiceClient:
    settings = get_settings()
    return ServiceClient(
        base_url=settings.async_api.base_url,
        timeout=settings.async_api.timeout,
{%- if cookiecutter.auth_method == "bearer_token" %}
        api_key=settings.async_api.api_key,
{%- endif %}
    )


async def trigger_async_operation(
    operation: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Trigger a generic async operation (HTTP 201/202 Accepted).

    Args:
        operation: The operation/endpoint path (e.g. "workflows/start").
        payload: The request body.

    Returns:
        Dict with correlation_id and status.
    """
    client = _get_client()
    try:
        response = await client.post(f"/{operation}", json=payload)
        return {
            "status": "accepted",
            "status_code": response.status_code,
            "correlation_id": response.headers.get("x-correlation-id", ""),
            "body": response.json() if response.content else {},
        }
    finally:
        await client.close()


async def send_quote_for_approval(
    quote_payload: dict[str, Any],
) -> dict[str, Any]:
    """Send a quote/proposal to an external system for approval.

    The downstream system processes the quote and calls back via the
    inbound webhook (``POST /webhooks/async-result``) when the customer
    approves or rejects.

    Args:
        quote_payload: Quote details — line items, totals, terms, etc.
            Expected keys (adapt to your domain):
            - customer_id (str)
            - items (list[dict]): line items
            - total (float)
            - valid_until (str): ISO date

    Returns:
        Dict with correlation_id to track the pending approval.
    """
    return await trigger_async_operation("quotes/send-for-approval", quote_payload)


async def request_document_generation(
    template_id: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    """Request async generation of a document (PDF, contract, report).

    Args:
        template_id: The document template identifier.
        variables: Template variables / merge fields.

    Returns:
        Dict with correlation_id. The generated document URL arrives
        via the inbound webhook.
    """
    return await trigger_async_operation(
        "documents/generate",
        {"template_id": template_id, "variables": variables},
    )
