"""PyMediate - A type-safe mediator pattern implementation for Python.

PyMediate is a modern implementation of the Mediator Pattern that provides
type-safe request routing with automatic response type inference. It's designed
for Python 3.12+ and integrates seamlessly with dataclasses and dependency
injection frameworks.

Key Features:
    - Type-safe: Full runtime validation with mypy support
    - Zero convention: Uses type inspection instead of naming conventions
    - Async/await support: Built-in async handlers and mediators via pymediate.aio
    - DI ready: Built-in dependency-injector integration
    - Dataclass friendly: Works seamlessly with @dataclass and Request[T]
    - Well tested: 122+ tests with 96%+ coverage

Quick Example:
    ```python
    from dataclasses import dataclass
    from pymediate import Request, Handler, Mediator, SimpleResolver

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

    resolver = SimpleResolver()
    resolver.register(CreateUser, CreateUserHandler())
    mediator = Mediator(resolver)

    response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"User {response.username} created with ID {response.user_id}")
    ```

Main Components:
    - Request: Base class for all requests
    - Handler: Base class for synchronous handlers
    - Mediator: Routes requests to handlers (sync version)
    - Resolver: Protocol for resolving handler instances
    - SimpleResolver: Dict-based resolver implementation
    - DependencyInjectorResolver: DI container integration

Async Support:
    For asynchronous operations, use the async variants from pymediate.aio:
    ```python
    from pymediate.aio import Handler, Mediator

    class AsyncHandler(Handler[CreateUser]):
        async def __call__(self, req: CreateUser) -> UserCreated:
            # Can use await here
            result = await async_database_operation(req)
            return UserCreated(user_id=result.id, username=req.username)

    mediator = Mediator(resolver)
    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    ```

For more information, see the documentation at https://sina-al.github.io/pymediate/
"""

from .errors import (
    DIContainerError,
    HandlerNotFoundError,
    HandlerTypeMismatchError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from .handler import Handler
from .mediator import Mediator
from .request import Request
from .resolvers import DependencyInjectorResolver, Resolver, SimpleResolver

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
