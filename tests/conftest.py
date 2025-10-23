"""Pytest configuration and fixtures for pymediate tests."""

from collections.abc import Generator

import pytest

# Check if dependency-injector is available
try:
    import dependency_injector  # noqa: F401

    HAS_DEPENDENCY_INJECTOR = True
except ImportError:
    HAS_DEPENDENCY_INJECTOR = False


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_di: mark test as requiring dependency-injector package"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked with requires_di if dependency-injector is not installed."""
    skip_di = pytest.mark.skip(reason="dependency-injector not installed")
    for item in items:
        if "requires_di" in item.keywords and not HAS_DEPENDENCY_INJECTOR:
            item.add_marker(skip_di)


@pytest.fixture(autouse=True)
def clear_registries() -> Generator[None]:
    """Clear handler registries after each test to ensure test isolation.

    This fixture runs automatically after each test to prevent test pollution
    from handler registrations. Handler classes should be defined within test
    functions (not at module level) to work properly with this cleanup.

    Note:
        - Request-response type mappings are NOT cleared (they're static type relationships)
        - Only handler registrations are cleared to ensure test isolation
        - Handler classes should be defined inside test functions for proper cleanup
    """
    yield
    # Clear only handler registry after test completes (keep request-response mappings)
    from pymediate._internal.registry import clear_handler_registry

    clear_handler_registry()
