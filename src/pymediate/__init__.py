"""PyMediate - A type-safe mediator pattern implementation for Python.

See tests for canonical usage examples.
"""

from pymediate.di_resolver import DependencyInjectorResolver
from pymediate.handler import Handler
from pymediate.mediator import Mediator
from pymediate.request import Request, request
from pymediate.resolver import Resolver, SimpleResolver

__all__ = [
    "Request",
    "request",
    "Handler",
    "Resolver",
    "SimpleResolver",
    "DependencyInjectorResolver",
    "Mediator",
]

__version__ = "0.1.0"
