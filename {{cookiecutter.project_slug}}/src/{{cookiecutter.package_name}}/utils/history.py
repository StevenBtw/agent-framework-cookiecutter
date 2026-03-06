"""In-memory conversation history.

Stores per-session message lists so the LLM sees prior turns.
Bounded by ``max_turns`` (pairs of user + assistant messages).

For production deployments, replace this with a Redis or database-
backed implementation that persists across restarts.

Usage::

    history = ConversationHistory(max_turns=20)
    history.add("user-1", "session-1", "user", "Hello")
    history.add("user-1", "session-1", "assistant", "Hi there!")
    messages = history.get("user-1", "session-1")
"""

from __future__ import annotations

from collections import deque
from typing import Any


class ConversationHistory:
    """In-memory, bounded conversation history keyed by user + session.

    Args:
        max_turns: Maximum number of *messages* to retain per session.
            Defaults to 40 (roughly 20 user/assistant pairs).
    """

    def __init__(self, max_turns: int = 40) -> None:
        self._max = max_turns
        self._sessions: dict[str, deque[dict[str, Any]]] = {}

    @staticmethod
    def _key(user_id: str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    def get(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        """Return a copy of the conversation history for a session."""
        key = self._key(user_id, session_id)
        buf = self._sessions.get(key)
        return list(buf) if buf else []

    def add(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Append a message to the session history."""
        key = self._key(user_id, session_id)
        if key not in self._sessions:
            self._sessions[key] = deque(maxlen=self._max)
        self._sessions[key].append({"role": role, "content": content})

    def clear(self, user_id: str, session_id: str) -> None:
        """Remove all history for a session."""
        self._sessions.pop(self._key(user_id, session_id), None)
