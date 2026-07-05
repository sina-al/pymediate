"""PyMediate - A type-safe mediator pattern implementation for Python.

PyMediate is a modern implementation of the Mediator Pattern that provides
type-safe request routing with automatic response type inference. It's designed
for Python 3.12+ and integrates seamlessly with dataclasses and dependency
injection frameworks.

Key Features:
    - Type-safe: Full runtime validation with mypy support
    - Async/await support: Built-in async handlers and mediators via pymediate.aio
    - DI ready: Built-in dependency-injector integration
    - Well tested: 95%+ coverage enforced in CI

Quick Example:
    ```python
    from dataclasses import dataclass
    from pymediate import Request, Handler, Mediator, Services

    @dataclass
    class UserCreated:
        user_id: int
        username: str

    @dataclass
    class CreateUser(Request[UserCreated]):
        username: str
        email: str

    class CreateUserHandler(Handler[CreateUser]):
        def __call__(self, req: CreateUser) -> UserCreated:
            return UserCreated(user_id=1, username=req.username)

    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"User {response.username} created with ID {response.user_id}")
    ```

Main Components:
    - Request: Base class for all requests
    - Handler: Base class for synchronous handlers
    - Mediator: Routes requests to handlers (sync version)
    - ServiceProvider: Protocol for resolving service instances
    - Services: Builder for registering services

Async Support:
    For asynchronous operations, use the async variants from pymediate.aio:
    ```python
    from pymediate import Services
    from pymediate.aio import Handler, Mediator

    class AsyncHandler(Handler[CreateUser]):
        async def __call__(self, req: CreateUser) -> UserCreated:
            # Can use await here
            result = await async_database_operation(req)
            return UserCreated(user_id=result.id, username=req.username)

    services = Services()
    services.add(AsyncHandler())
    provider = services.provider()
    mediator = Mediator(provider)
    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    ```

For more information, see the documentation at https://sina-al.github.io/pymediate/
"""

from .errors import (
    HandlerAlreadyRegisteredError,
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from .handler import Handler
from .mediator import Mediator
from .pipeline import PipelineBehavior
from .request import Request
from .service import ServiceNotFoundError, ServiceProvider, Services

__all__ = [
    "Request",
    "Handler",
    "Mediator",
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
    "ResponseTypeMismatchError",
]

__version__ = "0.1.3"
