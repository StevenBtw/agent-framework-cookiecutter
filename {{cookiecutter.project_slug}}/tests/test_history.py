"""Tests for conversation history."""

from __future__ import annotations

from {{ cookiecutter.package_name }}.utils.history import ConversationHistory


class TestConversationHistory:
    def test_empty_by_default(self) -> None:
        h = ConversationHistory()
        assert h.get("u1", "s1") == []

    def test_add_and_get(self) -> None:
        h = ConversationHistory()
        h.add("u1", "s1", "user", "Hello")
        h.add("u1", "s1", "assistant", "Hi!")
        msgs = h.get("u1", "s1")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Hello"}
        assert msgs[1] == {"role": "assistant", "content": "Hi!"}

    def test_max_turns_eviction(self) -> None:
        h = ConversationHistory(max_turns=4)
        for i in range(6):
            h.add("u1", "s1", "user", f"msg-{i}")
        msgs = h.get("u1", "s1")
        assert len(msgs) == 4
        # Oldest messages should have been evicted
        assert msgs[0]["content"] == "msg-2"

    def test_session_isolation(self) -> None:
        h = ConversationHistory()
        h.add("u1", "s1", "user", "Hello from s1")
        h.add("u1", "s2", "user", "Hello from s2")
        assert len(h.get("u1", "s1")) == 1
        assert len(h.get("u1", "s2")) == 1
        assert h.get("u1", "s1")[0]["content"] == "Hello from s1"

    def test_user_isolation(self) -> None:
        h = ConversationHistory()
        h.add("u1", "s1", "user", "User 1")
        h.add("u2", "s1", "user", "User 2")
        assert h.get("u1", "s1")[0]["content"] == "User 1"
        assert h.get("u2", "s1")[0]["content"] == "User 2"

    def test_clear(self) -> None:
        h = ConversationHistory()
        h.add("u1", "s1", "user", "Hello")
        h.clear("u1", "s1")
        assert h.get("u1", "s1") == []

    def test_get_returns_copy(self) -> None:
        h = ConversationHistory()
        h.add("u1", "s1", "user", "Hello")
        msgs = h.get("u1", "s1")
        msgs.append({"role": "user", "content": "injected"})
        assert len(h.get("u1", "s1")) == 1  # original unchanged
