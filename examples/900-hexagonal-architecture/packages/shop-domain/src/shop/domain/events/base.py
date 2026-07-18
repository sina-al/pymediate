"""Stable, self-describing contracts shared by domain events."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import ClassVar, Protocol, runtime_checkable

type EventValue = None | bool | int | float | str | list[EventValue] | dict[str, EventValue]
type EventPayload = dict[str, EventValue]


def validate_event_value(value: object, path: str = "payload") -> None:
    """Reject values that cannot be represented by portable JSON."""
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if isfinite(value):
            return
        raise ValueError(f"{path} is not JSON-compatible")
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_event_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for key, item in value.items():
            validate_event_value(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} is not JSON-compatible")


class AggregateType(StrEnum):
    """Stable aggregate categories used by the audit journal."""

    ORDER = "order"
    CUSTOMER = "customer"
    INVOICE = "invoice"
    STATEMENT = "statement"


@dataclass(frozen=True)
class AggregateRef:
    """Identify one aggregate without leaking its storage representation."""

    type: AggregateType
    id: str

    def __post_init__(self) -> None:
        if not isinstance(self.type, AggregateType):
            raise ValueError("aggregate type must be a known category")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("aggregate id must be non-empty text")


@runtime_checkable
class DomainEvent(Protocol):
    """A meaningful business fact that can be recorded for audit history."""

    event_name: ClassVar[str]
    schema_version: ClassVar[int]

    @property
    def aggregate(self) -> AggregateRef: ...

    def payload(self) -> EventPayload: ...
