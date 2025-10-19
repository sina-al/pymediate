"""Stub for DependencyInjectorResolver when dependency-injector is not installed."""

from typing import Any


class _DependencyInjectorResolverStub:
    """Stub that raises a helpful error when dependency-injector is not installed.

    This class is used when the 'dependency-injector' package is not available.
    It provides clear installation instructions when users try to use it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Raise an error with installation instructions."""
        raise ImportError(
            "DependencyInjectorResolver requires the 'dependency-injector' package.\n\n"
            "To use DependencyInjectorResolver, install PyMediate with the [di] extra:\n\n"
            "  pip install pymediate[di]\n"
            "  # or\n"
            "  uv add 'pymediate[di]'\n\n"
            "For more information, see:\n"
            "  https://sina-al.github.io/pymediate/guide/dependency-injection/\n"
            "  https://sina-al.github.io/pymediate/getting-started/installation/#optional-dependencies\n\n"
            "Troubleshooting: https://sina-al.github.io/pymediate/advanced/troubleshooting/#dependency-injector-not-available"
        )

    def __class_getitem__(cls, *args: Any) -> Any:
        """Handle type hints like DependencyInjectorResolver[T]."""
        return cls

    def __repr__(self) -> str:
        """Return a helpful representation."""
        return (
            "<DependencyInjectorResolver: requires 'dependency-injector' package. "
            "Install with: pip install pymediate[di]>"
        )
