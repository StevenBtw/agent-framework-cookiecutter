"""Shared Pydantic models for API requests, responses and WebSocket messages.

Centralises the data contracts so they can be reused across interfaces
(REST, WebSocket, CLI) and in tests without circular imports.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ------------------------------------------------------------------
# REST models
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Inbound chat request (REST and internal)."""

    message: str
    user_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Outbound chat response (REST)."""

    response: str
    session_id: str = ""


class AsyncResultPayload(BaseModel):
    """Inbound webhook payload when an async operation completes."""

    correlation_id: str
    session_id: str
    status: str
    data: dict[str, Any] = {}


# ------------------------------------------------------------------
# Tool result
# ------------------------------------------------------------------

class ToolResult(BaseModel):
    """Standardised result from a tool invocation."""

    success: bool
    data: Any = None
    error: str | None = None
    tool_name: str = ""


# ------------------------------------------------------------------
# Error response
# ------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Structured error returned by API endpoints."""

    code: str
    message: str
    request_id: str = ""
    details: dict[str, Any] = {}


# ------------------------------------------------------------------
# File upload
# ------------------------------------------------------------------

class UploadResponse(BaseModel):
    """Response returned after a successful file upload."""

    file_id: str
    filename: str
    size_bytes: int
    content_type: str | None = None


# ------------------------------------------------------------------
# WebSocket message types
# ------------------------------------------------------------------

class WSMessage(BaseModel):
    """Base WebSocket message (discriminated by ``type``)."""

    type: str
    data: Any = None


class WSTokenMessage(WSMessage):
    type: str = "token"
    data: str = ""


class WSDoneMessage(WSMessage):
    type: str = "done"
    data: None = None


class WSErrorMessage(WSMessage):
    type: str = "error"
    data: str = ""
    request_id: str = ""
