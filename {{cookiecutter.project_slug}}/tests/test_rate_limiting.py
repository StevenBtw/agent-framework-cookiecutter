"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import time
from unittest.mock import patch

from {{ cookiecutter.package_name }}.utils.rate_limiting import TokenBucket


class TestTokenBucket:
    def test_allows_burst(self) -> None:
        limiter = TokenBucket(rate=1.0, capacity=3)
        assert limiter.allow("a") is True
        assert limiter.allow("a") is True
        assert limiter.allow("a") is True

    def test_denies_after_burst(self) -> None:
        limiter = TokenBucket(rate=1.0, capacity=2)
        limiter.allow("a")
        limiter.allow("a")
        assert limiter.allow("a") is False

    def test_refills_over_time(self) -> None:
        limiter = TokenBucket(rate=10.0, capacity=1)
        limiter.allow("a")  # consume the one token
        assert limiter.allow("a") is False

        # Simulate time passing (0.2s at 10 tokens/sec = 2 tokens)
        with patch.object(time, "monotonic", return_value=time.monotonic() + 0.2):
            assert limiter.allow("a") is True

    def test_separate_keys(self) -> None:
        limiter = TokenBucket(rate=1.0, capacity=1)
        limiter.allow("a")
        assert limiter.allow("a") is False
        assert limiter.allow("b") is True  # different key, fresh bucket

    def test_evicts_oldest_key(self) -> None:
        limiter = TokenBucket(rate=1.0, capacity=1)
        # Fill up to MAX_KEYS
        from {{ cookiecutter.package_name }}.utils import rate_limiting

        original_max = rate_limiting.MAX_KEYS
        rate_limiting.MAX_KEYS = 3
        try:
            limiter.allow("a")
            limiter.allow("b")
            limiter.allow("c")
            # This should evict "a"
            limiter.allow("d")
            assert "a" not in limiter._buckets
            assert "d" in limiter._buckets
        finally:
            rate_limiting.MAX_KEYS = original_max
