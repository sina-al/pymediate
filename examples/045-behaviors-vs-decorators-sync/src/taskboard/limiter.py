"""Rate-limiter implementations shared by both approaches in this example."""

from typing import Protocol


class RateLimitExceededError(Exception):
    """Raised when a key has exceeded its configured call count."""


class RateLimiter(Protocol):
    """Anything that can check whether a key is still within quota."""

    def check(self, key: str) -> None:
        """Raise RateLimitExceededError if `key` has exceeded its quota."""
        ...


class CallCountLimiter:
    """Allow ``limit`` calls per key, then reject later calls."""

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
    """Allow every call when rate limiting is disabled."""

    def check(self, key: str) -> None:
        """Do nothing; every key is always within quota."""
        return None
