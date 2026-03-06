"""Agent tools for external service integration.

Three tool categories, matching real-world integration patterns:

- **async_api**: Fire-and-forget operations (HTTP 201/202).
  Results arrive later via inbound webhook.
- **data_service**: Synchronous CRUD (GET/POST/PUT).
  Immediate response.
- **logic_service**: Synchronous request-response computations.
  Call a module, get results back.
"""

from {{ cookiecutter.package_name }}.tools.async_api import (
    trigger_async_operation,
    send_quote_for_approval,
    request_document_generation,
)
from {{ cookiecutter.package_name }}.tools.data_service import (
    get_entity,
    create_entity,
    update_entity,
    update_preferences,
)
from {{ cookiecutter.package_name }}.tools.logic_service import (
    execute_logic,
    calculate_quotation,
    fuzzy_search,
)

__all__ = [
    # Async (fire-and-forget)
    "trigger_async_operation",
    "send_quote_for_approval",
    "request_document_generation",
    # Data (synchronous CRUD)
    "get_entity",
    "create_entity",
    "update_entity",
    "update_preferences",
    # Logic (synchronous computation)
    "execute_logic",
    "calculate_quotation",
    "fuzzy_search",
]
