"""Tests for DependencyInjectorResolver stub when dependency-injector is not available."""

import pytest


def test_di_resolver_stub_error_message() -> None:
    """Test that the stub provides a helpful error message when instantiated."""
    # Import the stub directly to test it
    from pymediate.resolvers._di_stub import _DependencyInjectorResolverStub

    # Test that instantiation raises helpful ImportError
    with pytest.raises(ImportError) as exc_info:
        _DependencyInjectorResolverStub(container=None)

    error_message = str(exc_info.value)

    # Check that error message contains helpful information
    assert "dependency-injector" in error_message.lower()
    assert "pip install pymediate[di]" in error_message
    assert "https://sina-al.github.io/pymediate" in error_message
    assert "troubleshooting" in error_message.lower()
    assert "uv add 'pymediate[di]'" in error_message


def test_di_resolver_stub_repr() -> None:
    """Test that the stub class has a helpful repr."""
    from pymediate.resolvers._di_stub import _DependencyInjectorResolverStub

    # Test the class repr itself (not an instance, since __init__ raises)
    repr_str = str(_DependencyInjectorResolverStub)
    assert "_DependencyInjectorResolverStub" in repr_str


@pytest.mark.requires_di
def test_di_resolver_available_with_dependency() -> None:
    """Test that real resolver is available when dependency-injector is installed."""
    # If dependency-injector is available, we should get the real resolver
    from pymediate import DependencyInjectorResolver

    # Check it's the real class, not the stub
    assert "dependency_injector" in DependencyInjectorResolver.__module__
    assert "_di_stub" not in DependencyInjectorResolver.__module__

    # Should be able to check for the required methods
    assert hasattr(DependencyInjectorResolver, "resolve")


def test_di_resolver_in_all_exports() -> None:
    """Test that DependencyInjectorResolver is always in __all__."""
    from pymediate import resolvers

    assert "DependencyInjectorResolver" in resolvers.__all__

    # Also check main package
    import pymediate

    assert "DependencyInjectorResolver" in pymediate.__all__


def test_stub_has_required_behavior() -> None:
    """Test that the stub has the expected methods for type hints."""
    from pymediate.resolvers._di_stub import _DependencyInjectorResolverStub

    # Should support __class_getitem__ for type hints
    assert hasattr(_DependencyInjectorResolverStub, "__class_getitem__")

    # Test it works
    result = _DependencyInjectorResolverStub.__class_getitem__(int)
    assert result is _DependencyInjectorResolverStub
