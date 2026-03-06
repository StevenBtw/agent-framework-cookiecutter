"""Base HTTP client for tool integrations."""

from __future__ import annotations

from typing import Any

import httpx
{% if cookiecutter.auth_method == "managed_identity" %}
from azure.identity import DefaultAzureCredential
{% endif %}
from {{ cookiecutter.package_name }}.utils.errors import ToolHTTPError


class ServiceClient:
    """Async HTTP client with auth and retry support.

    Each tool service gets its own ServiceClient instance
    configured with the appropriate base URL and credentials.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
{%- if cookiecutter.auth_method == "bearer_token" %}
        api_key: str = "",
{%- endif %}
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
{%- if cookiecutter.auth_method == "bearer_token" %}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
{%- elif cookiecutter.auth_method == "managed_identity" %}
        # Acquire token via managed identity
        credential = DefaultAzureCredential()
        token = credential.get_token("https://management.azure.com/.default")
        headers["Authorization"] = f"Bearer {token.token}"
{%- endif %}

        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.get(path, params=params)
        self._check_status(response)
        return response

    async def post(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.post(path, json=json)
        self._check_status(response)
        return response

    async def put(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.put(path, json=json)
        self._check_status(response)
        return response

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        """Raise a structured :class:`ToolHTTPError` on non-2xx status."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ToolHTTPError(
                message=f"HTTP {exc.response.status_code} from {exc.request.url}",
                upstream_status=exc.response.status_code,
                upstream_body=exc.response.text,
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()
