"""Memory provider integration."""

from __future__ import annotations

from typing import Any

{% if cookiecutter.memory_provider == "azure-foundry" -%}
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MemorySearchOptions
from azure.identity import DefaultAzureCredential

from {{ cookiecutter.package_name }}.config import get_settings


class MemoryProvider:
    """Long-term memory using Azure AI Foundry Memory Stores.

    Uses the azure-ai-projects SDK to store and recall memories via
    the Foundry Agent Service memory API. Memories are scoped per user
    so each user gets an isolated memory partition.

    Requires:
    - A Foundry project with a memory store created
    - Chat model and embedding model deployments in the project
    - FOUNDRY_PROJECT_ENDPOINT and MEMORY_STORE_NAME in config
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )
        self._store_name = settings.memory_store_name

    async def store(self, content: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory by updating the memory store with conversation content.

        The Foundry memory API extracts and consolidates memories from
        conversation items. This is a long-running operation.
        """
        _ = metadata
        items = [{"role": "user", "content": content, "type": "message"}]

        update_poller = self._client.beta.memory_stores.begin_update_memories(
            name=self._store_name,
            scope=user_id,
            items=items,
            update_delay=0,
        )
        result = update_poller.result()

        if result.memory_operations:
            return result.memory_operations[0].memory_item.memory_id
        return ""

    async def recall(self, query: str, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search memories by query within the user's scope."""
        query_item = {"role": "user", "content": query, "type": "message"}

        search_response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=user_id,
            items=[query_item],
            options=MemorySearchOptions(max_memories=limit),
        )
        return [
            {
                "memory_id": m.memory_item.memory_id,
                "content": m.memory_item.content,
            }
            for m in search_response.memories
        ]

    async def get_all(self, *, user_id: str) -> list[dict[str, Any]]:
        """Retrieve static (user profile) memories for a user.

        Calls search_memories without items to get profile-level memories.
        """
        search_response = self._client.beta.memory_stores.search_memories(
            name=self._store_name,
            scope=user_id,
        )
        return [
            {
                "memory_id": m.memory_item.memory_id,
                "content": m.memory_item.content,
            }
            for m in search_response.memories
        ]

{%- elif cookiecutter.memory_provider == "grafeo-memory" -%}
import re
from pathlib import Path

from grafeo_memory import AsyncMemoryManager, MemoryConfig, OpenAIEmbedder
from openai import OpenAI

from {{ cookiecutter.package_name }}.config import get_settings


def _safe_filename(user_id: str) -> str:
    """Convert a user_id into a filesystem-safe filename.

    Supports composite IDs like ``prospect:abc123`` or
    ``customer:21-390hkjfw`` by replacing non-alphanumeric
    characters (except hyphens) with underscores.
    """
    return re.sub(r"[^a-zA-Z0-9\-]", "_", user_id)


class MemoryProvider:
    """Long-term memory using grafeo-memory.

    Fully embedded; no external servers required. Each user gets their
    own isolated ``.db`` file under ``GRAFEO_MEMORY_DB_DIR``, keyed by
    user_id. This supports composite identifiers like
    ``prospect:abc123`` or ``customer:21-390hkjfw``.

    Anonymous users get a transient random ID so their memories do not
    persist across sessions.

    Uses GrafeoDB with native vector search and graph relationships.
    The reconciliation loop automatically extracts facts, detects
    updates and removes stale information.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._db_dir = Path(settings.grafeo_memory_db_dir)
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._model = settings.grafeo_memory_model
        self._embedder = OpenAIEmbedder(OpenAI())
        self._managers: dict[str, AsyncMemoryManager] = {}

    def _get_manager(self, user_id: str) -> AsyncMemoryManager:
        """Return a per-user AsyncMemoryManager (created on first access).

        Each user gets an isolated .db file so memory is fully
        partitioned without relying on query-time user_id filters.
        """
        if user_id not in self._managers:
            db_path = self._db_dir / f"{_safe_filename(user_id)}.db"
            config = MemoryConfig(db_path=str(db_path))
            self._managers[user_id] = AsyncMemoryManager(
                self._model,
                config,
                embedder=self._embedder,
            )
        return self._managers[user_id]

    async def store(self, content: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> str:
        """Add a memory. The reconciliation loop extracts facts and
        reconciles them against existing memories (ADD/UPDATE/DELETE).
        """
        manager = self._get_manager(user_id)
        result = await manager.add(
            content,
            user_id=user_id,
            metadata=metadata,
        )
        if result:
            return result[0].memory_id or ""
        return ""

    async def recall(self, query: str, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search memories by semantic similarity and graph context."""
        manager = self._get_manager(user_id)
        results = await manager.search(query, user_id=user_id, k=limit)
        return [
            {
                "memory_id": r.memory_id,
                "content": r.text,
                "score": r.score,
            }
            for r in results
        ]

    async def get_all(self, *, user_id: str) -> list[dict[str, Any]]:
        """Retrieve all memories for a user."""
        manager = self._get_manager(user_id)
        results = await manager.get_all(user_id=user_id)
        return [
            {
                "memory_id": r.memory_id,
                "content": r.text,
            }
            for r in results
        ]

{%- elif cookiecutter.memory_provider == "mem0" -%}
from mem0 import MemoryClient

from {{ cookiecutter.package_name }}.config import get_settings


class MemoryProvider:
    """Long-term memory using mem0 (cloud platform).

    Uses the mem0 managed API which handles embedding, storage and
    retrieval server-side. Memories are scoped per user_id so each
    caller gets isolated recall.

    Requires a mem0 API key from https://app.mem0.ai.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = MemoryClient(api_key=settings.mem0_api_key)

    async def store(self, content: str, *, user_id: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory. mem0 extracts facts from the conversation."""
        messages = [{"role": "user", "content": content}]
        result = self._client.add(messages, user_id=user_id, metadata=metadata or {})
        # result is {"results": [{"id": "...", "memory": "...", "event": "ADD"}]}
        entries = result.get("results", []) if isinstance(result, dict) else result or []
        if entries and entries[0].get("id"):
            return entries[0]["id"]
        return ""

    async def recall(self, query: str, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search memories by semantic similarity."""
        results = self._client.search(query, filters={"user_id": user_id}, top_k=limit)
        return [
            {
                "memory_id": r.get("id", ""),
                "content": r.get("memory", ""),
                "score": r.get("score", 0.0),
            }
            for r in results
        ]

    async def get_all(self, *, user_id: str) -> list[dict[str, Any]]:
        """Retrieve all memories for a user."""
        results = self._client.get_all(filters={"user_id": user_id})
        return [
            {
                "memory_id": r.get("id", ""),
                "content": r.get("memory", ""),
            }
            for r in results
        ]
{%- endif %}
