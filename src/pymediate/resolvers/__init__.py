"""Resolvers for handler resolution.

This package provides different strategies for resolving handler instances
from request types. The Resolver protocol defines the interface, and various
implementations provide different resolution strategies.
"""

from pymediate.resolvers.base import Resolver
from pymediate.resolvers.simple import SimpleResolver

# DependencyInjectorResolver is optional - only available with [di] extra
try:
    from pymediate.resolvers.dependency_injector import DependencyInjectorResolver
except ImportError:
    # Provide a helpful stub that raises an error with installation instructions
    from pymediate.resolvers._di_stub import (
        _DependencyInjectorResolverStub as DependencyInjectorResolver,
    )

__all__ = ["Resolver", "SimpleResolver", "DependencyInjectorResolver"]
