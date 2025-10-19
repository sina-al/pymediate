"""Pytest configuration and fixtures for pymediate tests."""

import pytest

from pymediate.registry import clear_all_registries


@pytest.fixture(autouse=True)
def clear_registries():
    """Clear registries before each test to ensure test isolation.

    This fixture runs automatically before each test to prevent
    test pollution from class registrations.
    """
    yield

    # Clear all test registrations after each test
    clear_all_registries()
