"""Shared utilities: tracing, logging, errors, schemas, rate limiting, history."""

from {{ cookiecutter.package_name }}.utils.errors import (
    AgentError,
    RateLimitError,
    ToolError,
    ToolHTTPError,
)
from {{ cookiecutter.package_name }}.utils.history import ConversationHistory
from {{ cookiecutter.package_name }}.utils.logging import get_logger, setup_logging
from {{ cookiecutter.package_name }}.utils.tracing import (
    get_correlation_id,
    get_request_id,
    trace_request,
)

__all__ = [
    "AgentError",
    "ConversationHistory",
    "RateLimitError",
    "ToolError",
    "ToolHTTPError",
    "get_correlation_id",
    "get_logger",
    "get_request_id",
    "setup_logging",
    "trace_request",
]
