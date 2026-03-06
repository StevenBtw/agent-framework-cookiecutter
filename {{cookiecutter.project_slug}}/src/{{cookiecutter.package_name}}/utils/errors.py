"""Typed exception hierarchy and error formatting.

All agent-related exceptions inherit from :class:`AgentError` so they
can be caught uniformly.  Two helpers format errors for different
audiences:

- :func:`format_error_for_llm` — a safe, user-facing message the LLM
  can relay without leaking internals.
- :func:`format_error_response` — a structured dict for API responses,
  including the current ``request_id``.
"""

from __future__ import annotations

from typing import Any

from {{ cookiecutter.package_name }}.utils.tracing import get_request_id


# ------------------------------------------------------------------
# Exception hierarchy
# ------------------------------------------------------------------

class AgentError(Exception):
    """Base exception for all agent errors."""

    def __init__(
        self,
        message: str = "An internal error occurred",
        *,
        code: str = "AGENT_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


class ToolError(AgentError):
    """A tool failed to execute."""

    def __init__(
        self,
        message: str = "Tool execution failed",
        *,
        tool_name: str = "",
        code: str = "TOOL_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, details=details, status_code=status_code)
        self.tool_name = tool_name


class ToolHTTPError(ToolError):
    """A tool's upstream HTTP call returned a non-2xx status."""

    def __init__(
        self,
        message: str = "Upstream service error",
        *,
        tool_name: str = "",
        upstream_status: int = 0,
        upstream_body: str = "",
    ) -> None:
        super().__init__(
            message,
            tool_name=tool_name,
            code="TOOL_HTTP_ERROR",
            details={
                "upstream_status": upstream_status,
                "upstream_body": upstream_body[:500],
            },
        )
        self.upstream_status = upstream_status


class RateLimitError(AgentError):
    """Request was rate-limited."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: float = 60.0,
    ) -> None:
        super().__init__(
            message,
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            status_code=429,
        )
        self.retry_after = retry_after


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------

_LLM_MESSAGES: dict[str, str] = {
    "TOOL_ERROR": "I was unable to complete that action due to an internal error.",
    "TOOL_HTTP_ERROR": "The external service I tried to reach returned an error.",
    "RATE_LIMIT_EXCEEDED": "The service is temporarily busy. Please try again in a moment.",
    "AGENT_ERROR": "Something went wrong on my end. Please try again.",
}


def format_error_for_llm(error: AgentError) -> str:
    """Return a short, safe message the LLM can relay to the user."""
    return _LLM_MESSAGES.get(error.code, _LLM_MESSAGES["AGENT_ERROR"])


def format_error_response(error: AgentError) -> dict[str, Any]:
    """Return a structured error dict for API responses."""
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "request_id": get_request_id(),
            "details": error.details,
        }
    }
