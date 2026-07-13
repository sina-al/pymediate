"""A rate limiter — the dependency each cross-cutting approach calls through.

`FixedWindowLimiter` stands in for a real backend (e.g. Redis): a fixed quota per key, no
window reset in this demo. `AlwaysAllow` is the deterministic double you'd want in a test,
or in a bulk-import tool that shouldn't be throttled at all. The whole example is about how
cleanly each approach lets you swap one for the other.
"""

from typing import Protocol


class RateLimitExceededError(Exception):
    """Raised when a key has exceeded its quota for the current window."""


class RateLimiter(Protocol):
    """Anything that can check whether a key is still within quota."""

    def check(self, key: str) -> None:
        """Raise RateLimitExceededError if `key` has exceeded its quota."""
        ...


class FixedWindowLimiter:
    """A stand-in for a real backend: `limit` calls per key, then every call after raises."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._counts: dict[str, int] = {}

    def check(self, key: str) -> None:
        """Raise once `key` has been checked more than `limit` times."""
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        if count > self._limit:
            raise RateLimitExceededError(f"{key!r} exceeded {self._limit} calls")


class AlwaysAllow:
    """A deterministic double that never raises — what a test wants to substitute in."""

    def check(self, key: str) -> None:
        """Do nothing; every key is always within quota."""
        return None
