"""Transactional domain-event journal contracts for durable audit history."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from shop.domain.events.base import (
    AggregateType,
    DomainEvent,
    EventPayload,
    validate_event_value,
)


@dataclass(frozen=True)
class DomainEventRecord:
    """Immutable, versioned evidence of one successful business fact."""

    event_id: str
    event_type: str
    schema_version: int
    occurred_at: datetime
    aggregate_type: AggregateType
    aggregate_id: str
    payload: EventPayload

    @classmethod
    def from_event(cls, event: DomainEvent) -> "DomainEventRecord":
        """Assign durable metadata using only the self-describing domain event."""
        return cls(
            event_id=str(uuid4()),
            event_type=event.event_name,
            schema_version=event.schema_version,
            occurred_at=datetime.now(UTC),
            aggregate_type=event.aggregate.type,
            aggregate_id=event.aggregate.id,
            payload=event.payload(),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str):
            raise ValueError("domain event event_id must be a UUID")
        try:
            UUID(self.event_id)
        except ValueError:
            raise ValueError("domain event event_id must be a UUID") from None
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("domain event event_type must not be empty")
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version < 1
        ):
            raise ValueError("domain event schema_version must be a positive integer")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("domain event occurred_at must include a UTC offset")
        if (
            not isinstance(self.aggregate_type, AggregateType)
            or not isinstance(self.aggregate_id, str)
            or not self.aggregate_id.strip()
        ):
            raise ValueError("domain event aggregate identity must not be empty")
        if not isinstance(self.payload, dict):
            raise ValueError("domain event payload must be a JSON object")
        validate_event_value(self.payload, "domain_event.payload")


@runtime_checkable
class DomainEventJournal(Protocol):
    """Append domain evidence inside the caller's business transaction."""

    async def append(self, event: DomainEvent) -> DomainEventRecord: ...


@runtime_checkable
class DomainEventJournalReader(Protocol):
    """Read one aggregate's immutable event history in occurrence order."""

    def stream_domain_events(
        self, aggregate_type: AggregateType, aggregate_id: str
    ) -> AsyncIterator[DomainEventRecord]: ...
