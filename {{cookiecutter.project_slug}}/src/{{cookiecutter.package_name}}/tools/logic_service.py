"""Logic service tools for synchronous request-response computations.

For calling business logic / calculation / search modules and getting
results back immediately.

Real-world examples:
- Calculate a quotation or pricing estimate
- Run a fuzzy search across a product catalogue
- Evaluate eligibility rules or compliance checks
- Score a lead or compute a risk assessment
"""

from __future__ import annotations

from typing import Any

from {{ cookiecutter.package_name }}.config import get_settings
from {{ cookiecutter.package_name }}.tools.base import ServiceClient


def _get_client() -> ServiceClient:
    settings = get_settings()
    return ServiceClient(
        base_url=settings.logic_service.base_url,
        timeout=settings.logic_service.timeout,
{%- if cookiecutter.auth_method == "bearer_token" %}
        api_key=settings.logic_service.api_key,
{%- endif %}
    )


async def execute_logic(
    module: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Execute a business logic module and return the computed results.

    Args:
        module: The logic module/endpoint path (e.g. "pricing/calculate", "risk/assess").
        inputs: The input parameters for the computation.

    Returns:
        The computed results as a dict.
    """
    client = _get_client()
    try:
        response = await client.post(f"/{module}", json=inputs)
        return response.json()
    finally:
        await client.close()


async def calculate_quotation(
    line_items: list[dict[str, Any]],
    *,
    customer_id: str | None = None,
    discount_code: str | None = None,
) -> dict[str, Any]:
    """Calculate a quotation / pricing estimate.

    The agent calls this when a customer asks "How much would it cost
    to …" or provides details for a quote.

    Args:
        line_items: List of items, each with:
            - product_id (str)
            - quantity (int)
            - options (dict, optional): product-specific config
        customer_id: Optional — for customer-specific pricing tiers.
        discount_code: Optional — promotional discount code.

    Returns:
        Dict with line totals, subtotal, tax, discount, and grand total.
    """
    return await execute_logic("pricing/calculate", {
        "line_items": line_items,
        "customer_id": customer_id,
        "discount_code": discount_code,
    })


async def fuzzy_search(
    query: str,
    *,
    index: str = "products",
    limit: int = 10,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a fuzzy / semantic search against an index.

    The agent calls this when a customer describes what they're looking
    for in natural language and needs matching results.

    Args:
        query: Free-text search query.
        index: The search index name (e.g. "products", "articles", "faq").
        limit: Maximum results to return.
        filters: Optional structured filters (category, price range, etc.).

    Returns:
        Dict with ``results`` list and ``total_count``.
    """
    return await execute_logic("search/fuzzy", {
        "query": query,
        "index": index,
        "limit": limit,
        "filters": filters or {},
    })
