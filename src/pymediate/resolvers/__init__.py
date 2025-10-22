"""Resolvers for handler resolution.

This package provides different strategies for resolving handler instances
from request types. The Resolver protocol defines the interface, and various
implementations provide different resolution strategies.
"""

from typing import TYPE_CHECKING

from ._base import Resolver
from .simple import SimpleResolver

if TYPE_CHECKING:
    from .dependency_injector import DependencyInjectorResolver
else:
    try:
        from .dependency_injector import DependencyInjectorResolver
    except ImportError:
        # Provide a helpful stub that raises an error with installation instructions
        from ._di_stub import (
            _DependencyInjectorResolverStub as DependencyInjectorResolver,
        )

__all__ = ["Resolver", "SimpleResolver", "DependencyInjectorResolver"]
