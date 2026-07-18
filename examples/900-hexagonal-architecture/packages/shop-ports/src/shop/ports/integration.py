"""Versioned contracts that cross process and deployment boundaries."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Protocol, cast
from uuid import UUID, uuid4

from shop.domain.events.base import EventPayload, EventValue, validate_event_value

type JsonValue = EventValue
type JsonObject = EventPayload

_ENVELOPE_FIELDS = {"message_id", "event_type", "schema_version", "occurred_at", "payload"}


class IntegrationEvent(Protocol):
    """A typed application-owned contract ready to enter an outbox."""

    event_type: ClassVar[str]
    schema_version: ClassVar[int]

    def payload(self) -> JsonObject: ...


@dataclass(frozen=True)
class IntegrationMessage:
    """A validated envelope carrying one versioned integration event."""

    message_id: str
    event_type: str
    schema_version: int
    occurred_at: datetime
    payload: JsonObject

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, str):
            raise ValueError("integration message message_id must be a UUID")
        try:
            UUID(self.message_id)
        except ValueError:
            raise ValueError("integration message message_id must be a UUID") from None
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("integration message event_type must not be empty")
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version < 1
        ):
            raise ValueError("integration message schema_version must be a positive integer")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("integration message occurred_at must be in UTC")
        if not isinstance(self.payload, dict):
            raise ValueError("integration message payload must be a JSON object")
        validate_event_value(self.payload, "integration message payload")

    @classmethod
    def from_event(cls, event: IntegrationEvent) -> "IntegrationMessage":
        """Envelope one self-describing integration event with durable identity and time."""
        return cls(
            message_id=str(uuid4()),
            event_type=event.event_type,
            schema_version=event.schema_version,
            occurred_at=datetime.now(UTC),
            payload=event.payload(),
        )


def serialize_message(message: IntegrationMessage) -> str:
    """Serialize an integration envelope as strict, canonical JSON."""
    return json.dumps(
        {
            "message_id": message.message_id,
            "event_type": message.event_type,
            "schema_version": message.schema_version,
            "occurred_at": message.occurred_at.isoformat(),
            "payload": message.payload,
        },
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"integration message contains non-standard number {value}")


def deserialize_message(body: str) -> IntegrationMessage:
    """Parse and validate the exact integration envelope received from a broker."""
    value = json.loads(body, parse_constant=_reject_nonstandard_number)
    if not isinstance(value, dict):
        raise ValueError("integration message must be a JSON object")
    if set(value) != _ENVELOPE_FIELDS:
        raise ValueError(
            "integration message fields must be exactly: " + ", ".join(sorted(_ENVELOPE_FIELDS))
        )
    message_id = value["message_id"]
    event_type = value["event_type"]
    schema_version = value["schema_version"]
    occurred_at = value["occurred_at"]
    payload = value["payload"]
    if not isinstance(message_id, str) or not isinstance(event_type, str):
        raise ValueError("integration message identifiers must be strings")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise ValueError("integration message schema_version must be an integer")
    if not isinstance(occurred_at, str) or not isinstance(payload, dict):
        raise ValueError("integration message timestamp or payload has the wrong shape")
    try:
        timestamp = datetime.fromisoformat(occurred_at)
    except ValueError:
        raise ValueError("integration message occurred_at is not an ISO timestamp") from None
    return IntegrationMessage(
        message_id=message_id,
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=timestamp,
        payload=cast("JsonObject", payload),
    )
