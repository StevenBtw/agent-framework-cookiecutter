"""Tests for structured logging utilities."""

from __future__ import annotations

import json
import logging

import pytest

from {{ cookiecutter.package_name }}.utils.logging import (
    ContextFilter,
    DevFormatter,
    JsonFormatter,
    audit_log_fn,
    get_logger,
)
from {{ cookiecutter.package_name }}.utils.tracing import trace_request


@pytest.fixture(autouse=True)
def _reset_logging_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow setup_logging to run in each test."""
    import {{ cookiecutter.package_name }}.utils.logging as mod

    monkeypatch.setattr(mod, "_SETUP_DONE", False)


class TestContextFilter:
    def test_injects_ids(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        with trace_request(correlation_id="cid-1"):
            ContextFilter().filter(record)
        assert record.request_id != ""  # type: ignore[attr-defined]
        assert record.correlation_id == "cid-1"  # type: ignore[attr-defined]

    def test_empty_without_context(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        ContextFilter().filter(record)
        assert record.request_id == ""  # type: ignore[attr-defined]


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        record.request_id = "rid-1"  # type: ignore[attr-defined]
        record.correlation_id = "cid-1"  # type: ignore[attr-defined]
        output = JsonFormatter().format(record)
        data = json.loads(output)
        assert data["message"] == "hello"
        assert data["request_id"] == "rid-1"
        assert data["level"] == "INFO"

    def test_includes_extra_fields(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "hi", (), None)
        record.request_id = ""  # type: ignore[attr-defined]
        record.correlation_id = ""  # type: ignore[attr-defined]
        record.tool = "get_entity"  # type: ignore[attr-defined]
        data = json.loads(JsonFormatter().format(record))
        assert data["tool"] == "get_entity"


class TestDevFormatter:
    def test_readable_output(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "started", (), None)
        record.request_id = "abc"  # type: ignore[attr-defined]
        output = DevFormatter().format(record)
        assert "abc" in output
        assert "started" in output
        assert "INFO" in output


class TestGetLogger:
    def test_returns_logger(self) -> None:
        logger = get_logger("myapp.test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "myapp.test"


class TestAuditLogFn:
    async def test_logs_event(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="audit"):
            await audit_log_fn({"event": "tool_call_start", "tool": "get_entity"})
        assert "tool_call_start" in caplog.text
