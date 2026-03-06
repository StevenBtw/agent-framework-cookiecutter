"""Request tracing via context variables.

Provides per-request ``request_id`` and ``correlation_id`` that propagate
through async call chains.  Other utilities (logging, errors) read these
to annotate their output automatically.

Usage::

    with trace_request(correlation_id="from-header"):
        # Everything in this block sees the same IDs
        rid = get_request_id()
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def generate_id() -> str:
    """Return a short unique identifier (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def get_request_id() -> str:
    return request_id_var.get()


def get_correlation_id() -> str:
    return correlation_id_var.get()


@contextmanager
def trace_request(
    correlation_id: str | None = None,
) -> Generator[None, None, None]:
    """Set request and correlation IDs for the duration of a block.

    If ``correlation_id`` is not provided, one is generated.
    A fresh ``request_id`` is always generated.
    """
    rid_token: Token[str] = request_id_var.set(generate_id())
    cid_token: Token[str] = correlation_id_var.set(
        correlation_id or generate_id()
    )
    try:
        yield
    finally:
        request_id_var.reset(rid_token)
        correlation_id_var.reset(cid_token)
