"""PyMediate - A type-safe mediator pattern implementation for Python.

See tests for canonical usage examples.
"""

from pymediate.di_resolver import DependencyInjectorResolver
from pymediate.errors import (
    DIContainerError,
    HandlerNotFoundError,
    HandlerTypeMismatchError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from pymediate.handler import Handler
from pymediate.mediator import Mediator
from pymediate.request import Request
from pymediate.resolver import Resolver, SimpleResolver

__all__ = [
    "Request",
    "Handler",
    "Resolver",
    "SimpleResolver",
    "DependencyInjectorResolver",
    "Mediator",
    # Errors
    "PyMediateError",
    "HandlerNotFoundError",
    "HandlerTypeMismatchError",
    "InvalidHandlerSignatureError",
    "InvalidRequestTypeError",
    "DIContainerError",
    "ResponseTypeMismatchError",
]

__version__ = "0.1.0"
