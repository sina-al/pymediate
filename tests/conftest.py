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
    """Clear registries before each test to ensure test isolation.

    This fixture runs automatically before each test to prevent
    test pollution from class registrations.

    Note: We don't clear registries here because handler classes are typically
    defined at module level and registered during import. Clearing would remove
    those registrations. Instead, tests should be written to be independent.
    """
    yield
    # No-op: Registry clearing disabled to allow module-level handler definitions
