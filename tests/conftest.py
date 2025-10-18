"""Pytest configuration and fixtures for pymediate tests."""

import pytest

from pymediate.registry import _HANDLER_REGISTRY, _REQUEST_REGISTRY


@pytest.fixture(autouse=True)
def clear_registries():
    """Clear registries before each test to ensure test isolation.

    This fixture runs automatically before each test to prevent
    test pollution from class registrations.
    """
    # Save initial state (in case there are any built-in registrations)
    initial_request_registry = _REQUEST_REGISTRY.copy()
    initial_handler_registry = _HANDLER_REGISTRY.copy()

    yield

    # Clear all test registrations
    _REQUEST_REGISTRY.clear()
    _HANDLER_REGISTRY.clear()

    # Restore initial state
    _REQUEST_REGISTRY.update(initial_request_registry)
    _HANDLER_REGISTRY.update(initial_handler_registry)
