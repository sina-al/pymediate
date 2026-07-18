"""Common structured-logging capability used across the application."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Logger(Protocol):
    """Record named events with structured, non-sensitive metadata."""

    def info(self, event: str, **metadata: object) -> None: ...

    def error(self, event: str, **metadata: object) -> None: ...
