"""Knowledge/RAG provider stub.

Implement your own retrieval-augmented generation pipeline here.
This stub provides the interface contract for knowledge retrieval
that the agent uses to ground its responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeResult:
    """A single knowledge retrieval result."""

    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeProvider:
    """Stub knowledge provider. Replace with your RAG implementation.

    Example integrations:
    - Azure AI Search
    - Elasticsearch
    - ChromaDB / Qdrant / Weaviate
    - Custom document store
    """

    async def search(self, query: str, *, top_k: int = 5) -> list[KnowledgeResult]:
        """Search the knowledge base for relevant documents.

        Args:
            query: The search query.
            top_k: Maximum number of results to return.

        Returns:
            A list of knowledge results ranked by relevance.
        """
        # TODO: Implement your knowledge retrieval logic here.
        _ = query, top_k
        return []

    async def ingest(self, content: str, *, source: str = "", metadata: dict[str, Any] | None = None) -> str:
        """Ingest a document into the knowledge base.

        Args:
            content: The document content.
            source: The document source identifier.
            metadata: Additional metadata.

        Returns:
            The document ID.
        """
        # TODO: Implement your document ingestion logic here.
        _ = content, source, metadata
        return ""
