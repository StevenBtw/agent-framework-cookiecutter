"""Inbound user authentication for API requests.

Supports two identity provider modes:

- **Entra ID** (Azure AD): Validates JWT tokens issued by Microsoft Entra ID.
  Extracts ``oid`` (object ID) as the user identifier.
- **Custom OIDC**: Validates JWT tokens from any OpenID Connect provider.
  Extracts ``sub`` as the user identifier.

Both modes fetch the provider's JWKS (JSON Web Key Set) to verify token
signatures. Set ``AUTH_ENABLED=false`` to disable authentication entirely
(useful for local development).

Anonymous (unauthenticated) requests are allowed but get a transient
session-scoped user_id so they cannot recall memories across sessions.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from fastapi import Request

from {{ cookiecutter.package_name }}.config import get_settings

ANONYMOUS_PREFIX = "anon-"


class UserIdentity:
    """Resolved identity for the current request."""

    def __init__(self, user_id: str, *, authenticated: bool = False, claims: dict[str, Any] | None = None) -> None:
        self.user_id = user_id
        self.authenticated = authenticated
        self.claims = claims or {}

    @property
    def is_anonymous(self) -> bool:
        return not self.authenticated


@lru_cache
def _get_jwks_client() -> Any:
    """Create a cached PyJWKClient for the configured identity provider."""
    import jwt  # PyJWT

    settings = get_settings()
    if not settings.auth_jwks_url:
        return None
    return jwt.PyJWKClient(settings.auth_jwks_url)


def _decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token against the configured identity provider."""
    import jwt  # PyJWT

    settings = get_settings()
    jwks_client = _get_jwks_client()

    if jwks_client is None:
        raise ValueError("JWKS URL not configured")

    signing_key = jwks_client.get_signing_key_from_jwt(token)

    decode_options: dict[str, Any] = {
        "algorithms": ["RS256"],
    }

    if settings.auth_audience:
        decode_options["audience"] = settings.auth_audience

    if settings.auth_issuer:
        decode_options["issuer"] = settings.auth_issuer

    return jwt.decode(
        token,
        signing_key.key,
        **decode_options,
    )


async def resolve_identity(request: Request) -> UserIdentity:
    """FastAPI dependency that resolves the caller's identity.

    Looks for an ``Authorization: Bearer <token>`` header. If present and
    valid, returns an authenticated ``UserIdentity`` with the user_id
    extracted from the token claims. Otherwise returns an anonymous identity.
    """
    settings = get_settings()

    if not settings.auth_enabled:
        # Auth disabled; trust the user_id from the request body if present
        return UserIdentity(
            user_id=f"{ANONYMOUS_PREFIX}{uuid.uuid4().hex[:12]}",
            authenticated=False,
        )

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return UserIdentity(
            user_id=f"{ANONYMOUS_PREFIX}{uuid.uuid4().hex[:12]}",
            authenticated=False,
        )

    token = auth_header[7:]
    try:
        claims = _decode_token(token)
    except Exception:
        return UserIdentity(
            user_id=f"{ANONYMOUS_PREFIX}{uuid.uuid4().hex[:12]}",
            authenticated=False,
        )

    # Entra ID uses "oid" for the user object ID; standard OIDC uses "sub"
    user_id = claims.get("oid") or claims.get("sub") or ""
    if not user_id:
        return UserIdentity(
            user_id=f"{ANONYMOUS_PREFIX}{uuid.uuid4().hex[:12]}",
            authenticated=False,
        )

    return UserIdentity(
        user_id=str(user_id),
        authenticated=True,
        claims=claims,
    )
