"""In-memory token-bucket rate limiter.

Provides a simple per-key rate limiter suitable for single-process
deployments.  For multi-worker or distributed setups, swap this for
a Redis-backed implementation.

Usage with FastAPI::

    limiter = TokenBucket(rate=1.0, capacity=10)  # 1 token/sec, burst of 10

    @app.post("/chat", dependencies=[Depends(require_rate_limit)])
    async def chat(...): ...
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable

from {{ cookiecutter.package_name }}.utils.errors import RateLimitError

MAX_KEYS = 10_000


class TokenBucket:
    """Per-key token-bucket rate limiter.

    Args:
        rate: Tokens added per second.
        capacity: Maximum burst size (bucket capacity).
    """

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def allow(self, key: str) -> bool:
        """Check whether ``key`` may proceed.  Consumes one token if allowed."""
        now = time.monotonic()

        if key in self._buckets:
            tokens, last = self._buckets[key]
            self._buckets.move_to_end(key)
        else:
            tokens, last = float(self.capacity), now
            # Evict oldest entries if we exceed the max key count
            while len(self._buckets) >= MAX_KEYS:
                self._buckets.popitem(last=False)

        # Refill tokens based on elapsed time
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.rate)

        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True

        self._buckets[key] = (tokens, now)
        return False


{%- if cookiecutter.interface in ["fastapi", "both"] %}


def rate_limit_dependency(
    limiter: TokenBucket,
    key_func: Callable[..., str] | None = None,
) -> Any:
    """Create a FastAPI dependency that enforces rate limiting.

    Args:
        limiter: The ``TokenBucket`` instance.
        key_func: Callable that extracts a rate-limit key from a
            ``Request``.  Defaults to client IP.

    Returns:
        A FastAPI dependency (async callable).
    """
    from fastapi import Request

    async def _check(request: Request) -> None:
        if key_func is not None:
            key = key_func(request)
        else:
            key = request.client.host if request.client else "unknown"

        if not limiter.allow(key):
            raise RateLimitError(
                retry_after=1.0 / limiter.rate if limiter.rate else 60.0,
            )

    return _check
{%- endif %}
