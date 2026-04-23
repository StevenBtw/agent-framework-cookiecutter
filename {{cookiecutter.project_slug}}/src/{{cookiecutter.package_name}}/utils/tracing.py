"""Request tracing via context variables, with optional OpenTelemetry export.

Provides per-request ``request_id`` and ``correlation_id`` that propagate
through async call chains.  Other utilities (logging, errors) read these
to annotate their output automatically.

When the ``otel`` dependency group is installed and ``OTEL_ENABLED=true``,
traces are also exported to an OTLP collector (e.g. Jaeger, Grafana Tempo).

Usage::

    with trace_request(correlation_id="from-header"):
        # Everything in this block sees the same IDs
        rid = get_request_id()
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from {{ cookiecutter.package_name }}.config import Settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

_otel_tracer: Any = None

logger = logging.getLogger(__name__)


def generate_id() -> str:
    """Return a short unique identifier (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def get_request_id() -> str:
    return request_id_var.get()


def get_correlation_id() -> str:
    return correlation_id_var.get()


# ---------------------------------------------------------------------------
# OpenTelemetry (opt-in)
# ---------------------------------------------------------------------------

def setup_otel(settings: Settings) -> None:
    """Configure OpenTelemetry tracing if enabled and installed.

    Gracefully does nothing when the ``opentelemetry`` packages are absent.
    Install with ``uv sync --group otel``.
    """
    global _otel_tracer

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError:
        logger.debug("opentelemetry packages not installed — skipping OTEL setup (install with: uv sync --group otel)")
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _otel_tracer = trace.get_tracer(settings.otel_service_name)
    logger.info("OpenTelemetry tracing enabled — exporting to %s", settings.otel_exporter_otlp_endpoint)


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI app with OpenTelemetry (no-op if not installed)."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return
    FastAPIInstrumentor.instrument_app(app)


def instrument_httpx() -> None:
    """Instrument httpx with OpenTelemetry (no-op if not installed)."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except ImportError:
        return
    HTTPXClientInstrumentor().instrument()


# ---------------------------------------------------------------------------
# Core tracing context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace_request(
    correlation_id: str | None = None,
) -> Generator[None, None, None]:
    """Set request and correlation IDs for the duration of a block.

    If ``correlation_id`` is not provided, one is generated.
    A fresh ``request_id`` is always generated.

    When OpenTelemetry is enabled, also creates a span with the IDs
    as attributes.
    """
    rid = generate_id()
    cid = correlation_id or generate_id()
    rid_token: Token[str] = request_id_var.set(rid)
    cid_token: Token[str] = correlation_id_var.set(cid)

    if _otel_tracer is not None:
        with _otel_tracer.start_as_current_span(
            "request",
            attributes={"request_id": rid, "correlation_id": cid},
        ):
            try:
                yield
            finally:
                request_id_var.reset(rid_token)
                correlation_id_var.reset(cid_token)
    else:
        try:
            yield
        finally:
            request_id_var.reset(rid_token)
            correlation_id_var.reset(cid_token)
