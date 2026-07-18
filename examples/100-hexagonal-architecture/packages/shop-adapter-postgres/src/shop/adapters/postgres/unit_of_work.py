"""Task-owned PostgreSQL unit of work."""

import asyncio
from types import TracebackType
from typing import Any, Self

from .gateway import PostgresDbGateway, _TransactionHandle


class PostgresUnitOfWork:
    """Own one PostgreSQL transaction for exactly one handler invocation."""

    def __init__(self, database: PostgresDbGateway) -> None:
        self._database = database
        self._handle: _TransactionHandle | None = None
        self._owner: asyncio.Task[Any] | None = None
        self._used = False

    async def __aenter__(self) -> Self:
        if self._used:
            raise RuntimeError("PostgreSQL unit of work cannot be reused")
        owner = asyncio.current_task()
        if owner is None:
            raise RuntimeError("PostgreSQL unit of work requires an asyncio task")
        self._used = True
        self._owner = owner
        self._handle = await self._database._begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._handle is None:
            raise RuntimeError("PostgreSQL unit of work was not entered")
        if asyncio.current_task() is not self._owner:
            raise RuntimeError("PostgreSQL unit of work must exit from the task that entered it")
        handle, self._handle = self._handle, None
        await self._database._finish(handle, exc_type, exc_value, traceback)
