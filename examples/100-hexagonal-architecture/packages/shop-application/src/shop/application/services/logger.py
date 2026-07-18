"""Default structured logger shared by the Shop application."""

from typing import Protocol

import structlog


class _StructlogLogger(Protocol):
    def info(self, event: str, **metadata: object) -> object: ...

    def error(self, event: str, **metadata: object) -> object: ...


class StructlogLogger:
    """Implement the application logger with structlog's context-rich events."""

    def __init__(self, logger: _StructlogLogger | None = None) -> None:
        self._logger = structlog.get_logger("shop.application") if logger is None else logger

    def info(self, event: str, **metadata: object) -> None:
        self._logger.info(event, **metadata)

    def error(self, event: str, **metadata: object) -> None:
        self._logger.error(event, **metadata)
