"""Opaque ownership tokens for time-limited persistence claims."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class LeaseToken:
    """Identify the worker that currently owns a renewable lease."""

    value: UUID

    @classmethod
    def create(cls) -> "LeaseToken":
        """Create an unpredictable token for one newly acquired lease."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str | UUID) -> "LeaseToken":
        """Reconstruct a token stored by a persistence adapter."""
        return cls(value if isinstance(value, UUID) else UUID(value))

    def __str__(self) -> str:
        """Return the UUID representation used by databases."""
        return str(self.value)
