"""PyMediate - A type-safe mediator pattern implementation for Python.

PyMediate is a modern implementation of the Mediator Pattern that provides
type-safe request routing with automatic response type inference. It's designed
for Python 3.12+ and integrates seamlessly with dataclasses and dependency
injection frameworks.

Key Features:
    - Type-safe: Full runtime validation with mypy support
    - Async-first: The top-level API is async; sync variants live in pymediate.sync
    - DI ready: Built-in dependency-injector integration
    - Well tested: 95%+ coverage enforced in CI

Quick Example:
    ```python
    import asyncio
    from dataclasses import dataclass
    from pymediate import Mediator, Request, RequestHandler, Services

    @dataclass
    class UserCreated:
        user_id: int
        username: str

    @dataclass
    class CreateUser(Request[UserCreated]):
        username: str
        email: str

    class CreateUserHandler(RequestHandler[CreateUser]):
        async def __call__(self, req: CreateUser) -> UserCreated:
            return UserCreated(user_id=1, username=req.username)

    async def main():
        services = Services()
        services.add(CreateUserHandler())
        provider = services.provider()
        mediator = Mediator(provider)

        response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
        print(f"User {response.username} created with ID {response.user_id}")

    asyncio.run(main())
    ```

Main Components:
    - Request: Base class for all requests
    - RequestHandler: Base class for asynchronous handlers
    - Mediator: Routes requests to handlers and publishes events (async version)
    - Event: Base class for events published to zero or more handlers
    - EventHandler: Base class for asynchronous event handlers
    - ServiceProvider: Protocol for resolving service instances
    - Services: Builder for registering services

Sync Support:
    For synchronous operations, use the sync variants from pymediate.sync -
    the same API with plain `def` handlers and a blocking `send()`:
    ```python
    from pymediate.sync import Mediator, RequestHandler, Services

    class SyncHandler(RequestHandler[CreateUser]):
        def __call__(self, req: CreateUser) -> UserCreated:
            return UserCreated(user_id=1, username=req.username)

    services = Services()
    services.add(SyncHandler())
    provider = services.provider()
    mediator = Mediator(provider)
    response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
    ```

For more information, see the documentation at https://pymediate.sina-al.uk
"""

from importlib.metadata import PackageNotFoundError, version

from .errors import (
    HandlerAlreadyRegisteredError,
    HandlerNotFoundError,
    InvalidEventTypeError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from .event import Event, EventHandler
from .handler import RequestHandler
from .mediator import Mediator
from .pipeline import PipelineBehavior
from .request import Request
from .service import ServiceNotFoundError, ServiceProvider, Services

__all__ = [
    "Request",
    "RequestHandler",
    "Mediator",
    # Events
    "Event",
    "EventHandler",
    # Service Provider
    "ServiceProvider",
    "Services",
    "ServiceNotFoundError",
    # Pipeline
    "PipelineBehavior",
    # Errors
    "PyMediateError",
    "HandlerNotFoundError",
    "HandlerAlreadyRegisteredError",
    "InvalidHandlerSignatureError",
    "InvalidRequestTypeError",
    "InvalidEventTypeError",
    "ResponseTypeMismatchError",
]

# The distribution version is derived from git tags at build time (hatch-vcs); the
# installed package metadata is the only source of truth for it at runtime.
try:
    __version__ = version("pymediate")
except PackageNotFoundError:  # pragma: no cover - source tree used without an install
    __version__ = "0.0.0+unknown"
