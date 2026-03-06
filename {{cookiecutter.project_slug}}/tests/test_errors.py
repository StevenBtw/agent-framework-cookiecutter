"""Tests for error utilities."""

from __future__ import annotations

from {{ cookiecutter.package_name }}.utils.errors import (
    AgentError,
    RateLimitError,
    ToolError,
    ToolHTTPError,
    format_error_for_llm,
    format_error_response,
)
from {{ cookiecutter.package_name }}.utils.tracing import trace_request


class TestExceptionHierarchy:
    def test_agent_error_is_exception(self) -> None:
        assert issubclass(AgentError, Exception)

    def test_tool_error_inherits_agent_error(self) -> None:
        assert issubclass(ToolError, AgentError)

    def test_tool_http_error_inherits_tool_error(self) -> None:
        assert issubclass(ToolHTTPError, ToolError)

    def test_rate_limit_error_inherits_agent_error(self) -> None:
        assert issubclass(RateLimitError, AgentError)

    def test_tool_error_has_tool_name(self) -> None:
        err = ToolError("fail", tool_name="get_entity")
        assert err.tool_name == "get_entity"
        assert err.status_code == 502

    def test_tool_http_error_captures_upstream(self) -> None:
        err = ToolHTTPError(
            "bad gateway",
            tool_name="get_entity",
            upstream_status=503,
            upstream_body="Service Unavailable",
        )
        assert err.upstream_status == 503
        assert err.details["upstream_body"] == "Service Unavailable"

    def test_tool_http_error_truncates_body(self) -> None:
        err = ToolHTTPError(upstream_body="x" * 1000)
        assert len(err.details["upstream_body"]) == 500

    def test_rate_limit_error_defaults(self) -> None:
        err = RateLimitError()
        assert err.status_code == 429
        assert err.retry_after == 60.0


class TestFormatErrorForLlm:
    def test_tool_error_message(self) -> None:
        err = ToolError("connection refused", tool_name="get_entity")
        msg = format_error_for_llm(err)
        assert "unable" in msg.lower()
        # Should not leak the actual error message
        assert "connection refused" not in msg

    def test_rate_limit_message(self) -> None:
        msg = format_error_for_llm(RateLimitError())
        assert "busy" in msg.lower() or "try again" in msg.lower()

    def test_unknown_code_falls_back(self) -> None:
        err = AgentError("oops", code="UNKNOWN_CODE")
        msg = format_error_for_llm(err)
        assert "went wrong" in msg.lower()


class TestFormatErrorResponse:
    def test_structure(self) -> None:
        err = ToolError("fail", tool_name="get_entity")
        resp = format_error_response(err)
        assert "error" in resp
        assert resp["error"]["code"] == "TOOL_ERROR"
        assert resp["error"]["message"] == "fail"

    def test_includes_request_id(self) -> None:
        with trace_request():
            err = AgentError("oops")
            resp = format_error_response(err)
            assert resp["error"]["request_id"] != ""
