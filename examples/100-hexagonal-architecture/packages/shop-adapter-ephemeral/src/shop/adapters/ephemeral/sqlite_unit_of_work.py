"""Task-owned SQLite unit of work."""

import asyncio
from types import TracebackType
from typing import Any, Self

from .sqlite import SqliteDbGateway


class SqliteUnitOfWork:
    """Own one SQLite transaction for exactly one handler invocation."""

    def __init__(self, database: SqliteDbGateway) -> None:
        self._database = database
        self._owner: asyncio.Task[Any] | None = None
        self._used = False
        self._active = False

    async def __aenter__(self) -> Self:
        if self._used:
            raise RuntimeError("SQLite unit of work cannot be reused")
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("SQLite unit of work requires an asyncio task")
        self._used = True
        self._owner = task
        await self._database._begin()
        self._active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._active:
            raise RuntimeError("SQLite unit of work was not entered")
        if asyncio.current_task() is not self._owner:
            raise RuntimeError("SQLite unit of work must exit from the task that entered it")
        try:
            await self._database._finish(exc_type, exc_value, traceback)
        finally:
            self._active = False
