"""Lifecycle fixtures owned by the ephemeral adapter tests."""

from collections.abc import AsyncIterator

import pytest

from shop.adapters.ephemeral import SqliteDbGateway


@pytest.fixture
async def database() -> AsyncIterator[SqliteDbGateway]:
    """Yield an initialized SQLite gateway and close it after each test."""
    async with SqliteDbGateway() as database:
        yield database
