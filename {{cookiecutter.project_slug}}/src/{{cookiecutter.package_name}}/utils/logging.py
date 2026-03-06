"""Structured logging with request context.

Sets up Python logging with two formatters:

- **JsonFormatter** — one JSON object per line, suitable for log aggregators.
- **DevFormatter** — coloured, human-readable output for local development.

Both formatters automatically include ``request_id`` and ``correlation_id``
from :mod:`tracing` when available.

Usage::

    from {{ cookiecutter.package_name }}.utils.logging import setup_logging, get_logger

    setup_logging(json_output=False, level="DEBUG")
    logger = get_logger(__name__)
    logger.info("server started", extra={"port": 8000})
"""

from __future__ import annotations

import json as _json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from {{ cookiecutter.package_name }}.utils.tracing import get_correlation_id, get_request_id

_SETUP_DONE = False


# ------------------------------------------------------------------
# Filter that injects tracing context into every LogRecord
# ------------------------------------------------------------------

class ContextFilter(logging.Filter):
    """Injects ``request_id`` and ``correlation_id`` into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        return True


# ------------------------------------------------------------------
# Formatters
# ------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Emits one JSON line per log record."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
            "correlation_id": getattr(record, "correlation_id", ""),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields the caller passed
        for key in ("port", "tool", "session_id", "user_id", "event", "args"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return _json.dumps(entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        rid = getattr(record, "request_id", "") or "-"
        msg = record.getMessage()
        base = f"[{ts}] {record.levelname:<7} {rid} | {msg}"
        if record.exc_info and record.exc_info[1]:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

def setup_logging(*, json_output: bool = False, level: str = "INFO") -> None:
    """Configure the root logger.

    Safe to call multiple times; only the first call takes effect.
    """
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    _SETUP_DONE = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter() if json_output else DevFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring setup has run."""
    if not _SETUP_DONE:
        setup_logging()
    return logging.getLogger(name)


# ------------------------------------------------------------------
# Audit log callback (for AuditLogFilter)
# ------------------------------------------------------------------

_audit_logger = logging.getLogger("audit")


async def audit_log_fn(entry: dict[str, Any]) -> None:
    """Async callback compatible with ``AuditLogFilter(log_fn=...)``."""
    _audit_logger.info(
        entry.get("event", "audit"),
        extra={k: v for k, v in entry.items() if k != "event"},
    )
