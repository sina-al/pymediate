"""Fixtures shared by tests at the application's mediator boundary."""

from collections.abc import AsyncIterator

import pytest

from shop.bindings.loading import load_wiring

from .support import ApplicationHarness


@pytest.fixture
async def application() -> AsyncIterator[ApplicationHarness]:
    """Yield a production-shaped graph while its selected resources are active."""
    wiring = load_wiring()
    async with wiring.activate("application"):
        yield ApplicationHarness.create(wiring)
