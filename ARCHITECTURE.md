# PyMediate: Architecture and Design Philosophy

## Table of Contents

1. [Introduction](#introduction)
2. [Project Goals and Motivations](#project-goals-and-motivations)
3. [Core Design Principles](#core-design-principles)
4. [Architecture Overview](#architecture-overview)
5. [Technical Deep Dive](#technical-deep-dive)
6. [Usage Patterns](#usage-patterns)
7. [Contributing Guidelines](#contributing-guidelines)
8. [Future Direction](#future-direction)

---

## Introduction

**PyMediate** is a type-safe implementation of the Mediator pattern for Python 3.10+, designed to provide compile-time type safety, runtime validation, and seamless dependency injection integration. The project emerged from a need to bring the benefits of strongly-typed mediator patterns (common in statically-typed languages like C# with MediatR) to Python while respecting Python's dynamic nature and embracing modern type hinting capabilities.

The mediator pattern decouples request senders from request handlers, promoting loose coupling and single responsibility. PyMediate takes this further by eliminating boilerplate, enforcing type safety, and providing automatic type inference through metaclass programming.

---

## Project Goals and Motivations

### Primary Goals

1. **Zero-Boilerplate Type Safety**
   - Users should write `Handler[MyRequest]` instead of `Handler[MyRequest, MyResponse]`
   - Response types should be automatically inferred from request definitions
   - Type errors should be caught by mypy at compile time AND at class definition time at runtime
   - No manual registry management required

2. **Flexibility Without Compromise**
   - Support simple use cases with `SimpleResolver` (dict-based lookup)
   - Support complex enterprise scenarios with dependency injection containers
   - Allow any DI framework through the `Resolver` protocol
   - Never lock users into specific frameworks or patterns

3. **Developer Experience Excellence**
   - IDE autocomplete should work perfectly (hence dataclass support)
   - Error messages should be clear and actionable
   - Configuration should be minimal
   - Testing should be straightforward

4. **Production-Ready Quality**
   - 100% test coverage on core modules
   - Type-checked with mypy in strict mode
   - Comprehensive integration tests
   - Clear separation of concerns

### Motivations

#### The Problem Space

In typical Python applications, request/response handling often looks like this:

```python
# Without PyMediate - lots of manual wiring
class UserService:
    def create_user(self, username: str, email: str) -> dict:
        # Business logic here
        return {"user_id": 1, "username": username}

# Somewhere else in the code
user_service = UserService()
result = user_service.create_user("alice", "alice@example.com")
# What type is result? IDE doesn't know!
```

This approach has several issues:
- **Tight coupling**: Consumers need to know about `UserService` directly
- **Type ambiguity**: Return type `dict` provides no type safety
- **No centralization**: Hard to add cross-cutting concerns (logging, validation, authorization)
- **Testing friction**: Mocking services requires more setup

#### The PyMediate Solution

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

@dataclass
class UserCreatedResponse:
    user_id: int
    username: str
    email: str

class CreateUserRequest(Request, response_type=UserCreatedResponse):
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email

# Handler only needs to specify request type - response type is inferred!
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Business logic
        return UserCreatedResponse(
            user_id=1,
            username=request.username,
            email=request.email
        )

# Setup (typically in DI container)
resolver = SimpleResolver()
resolver.register(CreateUserRequest, CreateUserHandler())
mediator = Mediator(resolver)

# Usage - fully type-safe!
response = mediator.send(CreateUserRequest("alice", "alice@example.com"))
# IDE knows: response is UserCreatedResponse
# Autocomplete works: response.user_id, response.username, response.email
```

Benefits achieved:
- **Decoupling**: Consumers only depend on `Mediator` and request types
- **Type safety**: mypy verifies handler return types match request response types
- **IDE support**: Full autocomplete and type inference
- **Centralization**: Mediator becomes a perfect place for pipelines (logging, validation, etc.)
- **Testing**: Easy to test handlers in isolation, easy to mock mediator

---

## Core Design Principles

### 1. Type Inference Over Explicit Declaration

**Principle**: If the type system can figure it out, don't make users repeat themselves.

**Implementation**:
- Request classes declare their response type once: `class MyRequest(Request, response_type=MyResponse)`
- This gets stored in `_REQUEST_REGISTRY` by `RequestMeta` metaclass
- Handler classes only specify request type: `class MyHandler(Handler[MyRequest])`
- `HandlerMeta` looks up the response type from `_REQUEST_REGISTRY` automatically
- Runtime validation ensures handlers return the correct type

**Why**: Reduces duplication, prevents mismatches, improves maintainability.

### 2. Fail Fast with Clear Messages

**Principle**: Catch errors at the earliest possible moment with actionable feedback.

**Implementation**:
- Type errors are caught at **class definition time** (not at call time)
- When a handler is defined with the wrong return type, `HandlerMeta.__new__` raises `TypeError`
- Error messages include class names and expected types:
  ```
  TypeError: MyHandler.__call__ must return UserResponse, got str
  ```

**Why**: Developers get immediate feedback, errors don't propagate to production.

### 3. Protocol-Based Extensibility

**Principle**: Define interfaces through protocols, not inheritance hierarchies.

**Implementation**:
- `Resolver` is a `Protocol`, not an abstract base class
- Any class with a `resolve(request_class) -> Handler` method works
- Enables duck typing while maintaining type safety
- `SimpleResolver` and `DependencyInjectorResolver` are peers, not subclasses

**Why**: Maximum flexibility, easy to add custom resolvers, follows Python idioms.

### 4. Separation of Concerns

**Principle**: Each module has a single, well-defined responsibility.

**Module Structure**:
```
src/pymediate/
├── registry.py          # Global type registries
├── request.py           # Request base class and metaclass
├── handler.py           # Handler base class, metaclass, and validation
├── resolver.py          # Resolver protocol and SimpleResolver
├── di_resolver.py       # Optional dependency-injector integration
├── mediator.py          # Mediator orchestration
└── __init__.py          # Public API
```

**Why**: Easy to understand, test, and extend. New contributors can quickly locate relevant code.

### 5. Runtime Validation + Static Type Checking

**Principle**: Leverage both runtime and compile-time safety mechanisms.

**Implementation**:
- **Metaclasses** validate types at class definition time (runtime)
- **Type hints** enable mypy to verify types at compile time (static)
- **Generic types** preserve type information for IDEs
- **Protocol** enables structural typing

**Example**:
```python
# This is caught by metaclass at class definition time:
class BadHandler(Handler[MyRequest]):
    def __call__(self, request: MyRequest) -> str:  # Wrong!
        return "hello"
# TypeError: BadHandler.__call__ must return MyResponse, got str

# This is caught by mypy at compile time:
response: MyResponse = mediator.send(MyRequest())
bad_access = response.nonexistent_field  # mypy error!
```

**Why**: Defense in depth - catch errors early, provide IDE support.

### 6. Optional Dependencies via Extras

**Principle**: Core functionality should have minimal dependencies. Advanced features can be opt-in.

**Implementation**:
- Core PyMediate has zero runtime dependencies
- `dependency-injector` is optional: `pip install pymediate[di]`
- `DependencyInjectorResolver` only imported if needed
- No import errors if extras not installed

**Why**: Lightweight core, no forced dependencies, pay only for what you use.

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Application Layer                        │
│  (User code: Requests, Handlers, Responses, DI Container)       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Mediator (mediator.py)                      │
│  • send(request) -> response                                     │
│  • Orchestrates request/response flow                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                    ┌────────┐
                    │Resolver│ (Protocol)
                    └────┬───┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐   ┌──────────────────────────────┐
│   SimpleResolver    │   │ DependencyInjectorResolver   │
│   (resolver.py)     │   │   (di_resolver.py) [OPTIONAL]│
│  • Dict-based       │   │  • Container-based           │
│  • Manual register  │   │  • Auto naming convention    │
└─────────────────────┘   └──────────────────────────────┘
          │                             │
          └──────────────┬──────────────┘
                         ▼
                   ┌──────────┐
                   │ Handler  │ (Generic[RequestType])
                   └────┬─────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Request Registry │ (registry.py)
              │  RequestType ->  │
              │  ResponseType    │
              └──────────────────┘
```

### Data Flow

1. **Request Definition** (Application Layer)
   ```python
   class MyRequest(Request, response_type=MyResponse):
       ...
   ```
   - `RequestMeta.__new__` registers `MyRequest -> MyResponse` in `_REQUEST_REGISTRY`

2. **Handler Definition** (Application Layer)
   ```python
   class MyHandler(Handler[MyRequest]):
       def __call__(self, request: MyRequest) -> MyResponse:
           ...
   ```
   - `HandlerMeta.__new__` extracts `MyRequest` from generic parameters
   - Looks up `MyResponse` from `_REQUEST_REGISTRY`
   - Validates `__call__` signature matches `(MyRequest) -> MyResponse`
   - Stores handler in `_HANDLER_REGISTRY` (optional, for introspection)

3. **Resolver Setup** (Application Layer)
   ```python
   resolver = SimpleResolver()
   resolver.register(MyRequest, MyHandler())
   ```
   - Associates request type with handler instance

4. **Mediator Creation** (Application Layer)
   ```python
   mediator = Mediator(resolver)
   ```
   - Mediator holds reference to resolver

5. **Request Execution** (Runtime)
   ```python
   response = mediator.send(MyRequest("data"))
   ```
   - `mediator.send()` calls `resolver.resolve(MyRequest)`
   - Resolver returns handler instance
   - Mediator calls `handler(request)`
   - Handler returns `MyResponse` instance
   - Response flows back to caller

### Type Information Flow

```
Request Definition
       │
       ├─> RequestMeta captures response_type
       │
       └─> _REQUEST_REGISTRY[MyRequest] = MyResponse
                           │
                           │
Handler Definition         │
       │                   │
       ├─> HandlerMeta extracts MyRequest from Handler[MyRequest]
       │                   │
       └─> Looks up ◄──────┘
           MyResponse
                │
                ├─> Validates __call__ signature
                │
                └─> Stores type info in handler._response_type
                                    │
                                    │
Mediator.send(request)              │
       │                            │
       └─> Resolver finds handler   │
                │                   │
                └─> Handler executes with full type context
```

---

## Technical Deep Dive

### Metaclass Programming

#### Why Metaclasses?

Python's metaclasses allow us to customize class creation. We use them for:
1. **Automatic registration** - Record types without manual calls
2. **Validation** - Check signatures before any instances are created
3. **Type extraction** - Pull generic type parameters from annotations

#### RequestMeta Implementation

```python
class RequestMeta(type):
    """Metaclass for Request that handles response type registration."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        response_type: type | None = None,
        **kwargs: Any
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Register the request -> response mapping
        if response_type is not None:
            _REQUEST_REGISTRY[cls] = response_type

        return cls
```

**Key insight**: The `response_type` parameter comes from class definition syntax:
```python
class MyRequest(Request, response_type=MyResponse):
    #                      ^^^^^^^^^^^^^^^^^^^^^^
    #                      This becomes a kwarg to __new__
    pass
```

#### HandlerMeta Implementation

```python
class HandlerMeta(type):
    """Metaclass for Handler that extracts and validates types."""

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs: Any) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        cls._request_type = None
        cls._response_type = None

        # CRITICAL: Use __orig_bases__ to get generic types before erasure
        if hasattr(cls, '__orig_bases__'):
            for base in cls.__orig_bases__:
                origin = get_origin(base)
                if origin is not None:
                    args = get_args(base)
                    if len(args) >= 1:
                        cls._request_type = args[0]

                        # Look up response type from registry
                        if cls._request_type in _REQUEST_REGISTRY:
                            cls._response_type = _REQUEST_REGISTRY[cls._request_type]
                            break

        # Validate __call__ signature if we have type info
        if cls._request_type is not None and cls._response_type is not None:
            if name != 'Handler':  # Skip base class
                _validate_call_signature(cls, cls._request_type, cls._response_type)

        return cls
```

**Critical detail**: `__orig_bases__` vs `bases`
- `bases` contains actual base classes after generic type erasure
- `__orig_bases__` contains original bases with generic parameters intact
- Example:
  ```python
  class MyHandler(Handler[MyRequest]):
      pass

  # During MyHandler.__new__:
  bases = (Handler,)  # Generic info lost!
  MyHandler.__orig_bases__ = (Handler[MyRequest],)  # Generic info preserved!
  ```

#### Type Validation

```python
def _validate_call_signature(
    cls: type,
    expected_request_type: type,
    expected_response_type: type
) -> None:
    """Validate that __call__ has correct signature."""

    if '__call__' not in cls.__dict__:
        raise TypeError(f"{cls.__name__} must implement __call__ method")

    call_method = cls.__dict__['__call__']
    sig = inspect.signature(call_method)

    # Check parameter types
    params = list(sig.parameters.values())
    if len(params) < 2:  # self, request
        raise TypeError(f"{cls.__name__}.__call__ must accept a request parameter")

    request_param = params[1]
    if request_param.annotation != expected_request_type:
        raise TypeError(
            f"{cls.__name__}.__call__ must accept {expected_request_type.__name__}, "
            f"got {request_param.annotation}"
        )

    # Check return type
    if sig.return_annotation != expected_response_type:
        raise TypeError(
            f"{cls.__name__}.__call__ must return {expected_response_type.__name__}, "
            f"got {sig.return_annotation}"
        )
```

**Why validate at class definition time?**
- Errors surface immediately when code is loaded, not when first called
- Prevents invalid handlers from ever being registered
- Works even if handler is never actually used in tests

### Resolver Protocol

#### Protocol Design

```python
from typing import Protocol, TypeVar

RequestType = TypeVar("RequestType", contravariant=True)

class Resolver(Protocol):
    """Protocol for request handler resolution.

    Implementations must provide a way to resolve request types to handlers.
    This enables dependency injection integration while maintaining type safety.
    """

    def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
        """Resolve a request class to its handler.

        Args:
            request_class: The request class to resolve

        Returns:
            Handler instance for the request

        Raises:
            ValueError: If no handler is registered for the request class
        """
        ...
```

**Why a Protocol instead of ABC?**
- Protocols enable structural subtyping (duck typing with type safety)
- No inheritance required - any class with matching signature works
- More Pythonic than rigid class hierarchies
- Easier to integrate third-party code

#### SimpleResolver Implementation

```python
class SimpleResolver:
    """Simple dictionary-based resolver for request handlers."""

    def __init__(self) -> None:
        self._handlers: dict[type, Handler] = {}

    def register(self, request_class: type[RequestType], handler: Handler[RequestType]) -> None:
        """Register a handler for a request class."""
        self._handlers[request_class] = handler

    def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
        """Resolve a request class to its handler."""
        if request_class not in self._handlers:
            raise ValueError(f"No handler registered for {request_class.__name__}")
        return self._handlers[request_class]
```

**Use case**: Simple applications, testing, prototyping.

#### DependencyInjectorResolver Implementation

```python
from dependency_injector import containers

class DependencyInjectorResolver:
    """Resolver that uses dependency-injector containers.

    This resolver follows a naming convention:
    - CreateUserRequest -> create_user_handler
    - SendEmailRequest -> send_email_handler

    The container should have providers with these names.
    """

    def __init__(self, container: containers.DeclarativeContainer):
        self._container = container

    def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
        handler_name = self._to_snake_case(
            request_class.__name__.removesuffix("Request")
        ) + "_handler"

        if not hasattr(self._container, handler_name):
            raise ValueError(
                f"No handler provider '{handler_name}' found in container "
                f"for {request_class.__name__}"
            )

        provider = getattr(self._container, handler_name)
        handler = provider()

        if not isinstance(handler, Handler):
            raise ValueError(
                f"Provider '{handler_name}' did not return a Handler instance"
            )

        return handler

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert PascalCase to snake_case."""
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                if name[i - 1].islower() or (
                    i < len(name) - 1 and name[i + 1].islower()
                ):
                    result.append("_")
            result.append(char.lower())
        return "".join(result)
```

**Use case**: Enterprise applications with complex dependency graphs.

**Container pattern**:
```python
class ApplicationContainer(containers.DeclarativeContainer):
    # Configuration
    config = providers.Configuration()

    # Services
    database = providers.Singleton(Database, connection_string=config.db.url)
    email_service = providers.Singleton(EmailService, smtp_host=config.smtp.host)

    # Handlers
    create_user_handler = providers.Factory(
        CreateUserHandler,
        database=database
    )
    send_email_handler = providers.Factory(
        SendEmailHandler,
        email_service=email_service
    )

    # Self-reference for resolver
    __self__ = providers.Self()

    # Mediator
    mediator = providers.Singleton(
        Mediator,
        resolver=providers.Singleton(DependencyInjectorResolver, container=__self__)
    )
```

### Mediator Implementation

```python
class Mediator:
    """Mediator for sending requests to handlers.

    The mediator acts as a central dispatcher, routing requests to their
    appropriate handlers via the configured resolver.
    """

    def __init__(self, resolver: Resolver):
        self._resolver = resolver

    def send(self, request: RequestType) -> Any:
        """Send a request and return its response.

        Args:
            request: The request instance to process

        Returns:
            The response from the handler

        Raises:
            ValueError: If no handler is registered for the request type
        """
        request_type = type(request)
        handler = self._resolver.resolve(request_type)
        return handler(request)
```

**Simplicity by design**: Mediator's only job is orchestration. This makes it easy to extend with:
- Logging pipelines
- Validation pipelines
- Authorization pipelines
- Performance monitoring
- Error handling

Example extension:
```python
class LoggingMediator(Mediator):
    def send(self, request: RequestType) -> Any:
        logger.info(f"Handling {type(request).__name__}")
        start = time.time()
        try:
            result = super().send(request)
            logger.info(f"Completed in {time.time() - start:.2f}s")
            return result
        except Exception as e:
            logger.error(f"Failed: {e}")
            raise
```

---

## Usage Patterns

### Pattern 1: Simple CRUD Operations

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

@dataclass
class UserDTO:
    id: int
    username: str
    email: str

class GetUserRequest(Request, response_type=UserDTO):
    def __init__(self, user_id: int):
        self.user_id = user_id

class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserDTO:
        # Database lookup
        return UserDTO(id=request.user_id, username="alice", email="alice@example.com")

# Setup
resolver = SimpleResolver()
resolver.register(GetUserRequest, GetUserHandler())
mediator = Mediator(resolver)

# Usage
user = mediator.send(GetUserRequest(user_id=1))
print(user.username)  # IDE autocomplete works!
```

### Pattern 2: Complex Business Logic with DI

```python
from dependency_injector import containers, providers

# Domain
@dataclass
class OrderPlacedResponse:
    order_id: str
    total_amount: float
    confirmation_email_sent: bool

class PlaceOrderRequest(Request, response_type=OrderPlacedResponse):
    def __init__(self, user_id: int, items: list[str]):
        self.user_id = user_id
        self.items = items

# Infrastructure
class EmailService:
    def send_confirmation(self, email: str, order_id: str) -> bool:
        # Send email
        return True

class PaymentGateway:
    def process_payment(self, amount: float) -> bool:
        # Process payment
        return True

# Handler with dependencies
class PlaceOrderHandler(Handler[PlaceOrderRequest]):
    def __init__(
        self,
        email_service: EmailService,
        payment_gateway: PaymentGateway
    ):
        self._email_service = email_service
        self._payment_gateway = payment_gateway

    def __call__(self, request: PlaceOrderRequest) -> OrderPlacedResponse:
        # Business logic
        total = len(request.items) * 10.0
        payment_ok = self._payment_gateway.process_payment(total)
        email_sent = self._email_service.send_confirmation("user@example.com", "ORD-123")

        return OrderPlacedResponse(
            order_id="ORD-123",
            total_amount=total,
            confirmation_email_sent=email_sent
        )

# DI Container
class ApplicationContainer(containers.DeclarativeContainer):
    email_service = providers.Singleton(EmailService)
    payment_gateway = providers.Singleton(PaymentGateway)

    place_order_handler = providers.Factory(
        PlaceOrderHandler,
        email_service=email_service,
        payment_gateway=payment_gateway
    )

    __self__ = providers.Self()
    mediator = providers.Singleton(
        Mediator,
        resolver=providers.Singleton(DependencyInjectorResolver, container=__self__)
    )

# Usage
container = ApplicationContainer()
mediator = container.mediator()
response = mediator.send(PlaceOrderRequest(user_id=1, items=["item1", "item2"]))
print(f"Order {response.order_id} placed: ${response.total_amount}")
```

### Pattern 3: Testing

```python
def test_place_order_handler():
    """Test handler in isolation without mediator."""
    # Arrange
    mock_email = Mock(spec=EmailService)
    mock_payment = Mock(spec=PaymentGateway)
    mock_email.send_confirmation.return_value = True
    mock_payment.process_payment.return_value = True

    handler = PlaceOrderHandler(
        email_service=mock_email,
        payment_gateway=mock_payment
    )

    request = PlaceOrderRequest(user_id=1, items=["item1", "item2"])

    # Act
    response = handler(request)

    # Assert
    assert response.order_id == "ORD-123"
    assert response.total_amount == 20.0
    mock_payment.process_payment.assert_called_once_with(20.0)
    mock_email.send_confirmation.assert_called_once()

def test_mediator_integration():
    """Test full integration with mediator."""
    resolver = SimpleResolver()
    resolver.register(
        PlaceOrderRequest,
        PlaceOrderHandler(EmailService(), PaymentGateway())
    )
    mediator = Mediator(resolver)

    response = mediator.send(PlaceOrderRequest(user_id=1, items=["item1"]))

    assert response.order_id is not None
    assert response.total_amount > 0
```

### Pattern 4: Nested Dataclasses for Complex Responses

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Address:
    street: str
    city: str
    country: str

@dataclass
class UserProfile:
    user_id: int
    username: str
    email: str
    address: Address
    created_at: datetime
    is_active: bool

class GetUserProfileRequest(Request, response_type=UserProfile):
    def __init__(self, user_id: int):
        self.user_id = user_id

class GetUserProfileHandler(Handler[GetUserProfileRequest]):
    def __call__(self, request: GetUserProfileRequest) -> UserProfile:
        return UserProfile(
            user_id=request.user_id,
            username="alice",
            email="alice@example.com",
            address=Address(
                street="123 Main St",
                city="Springfield",
                country="USA"
            ),
            created_at=datetime.now(),
            is_active=True
        )

# Usage - full type safety and autocomplete
profile = mediator.send(GetUserProfileRequest(user_id=1))
print(profile.address.city)  # IDE knows this is a string!
print(profile.created_at.year)  # IDE knows this is datetime!
```

---

## Contributing Guidelines

### For New Contributors

Welcome! PyMediate is designed to be easy to understand and extend. Here's how to get started:

#### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/pymediate.git
cd pymediate

# Install dependencies with uv (recommended) or pip
uv sync
# or
pip install -e ".[dev,di]"

# Run tests
uv run pytest

# Run type checking
uv run mypy src/pymediate/

# Run linting
uv run ruff check src/ tests/
```

#### Code Standards

1. **Type Hints**: All public APIs must have complete type hints
   ```python
   # Good
   def send(self, request: RequestType) -> Any:
       ...

   # Bad
   def send(self, request):
       ...
   ```

2. **Docstrings**: All public classes and methods need docstrings
   ```python
   def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
       """Resolve a request class to its handler.

       Args:
           request_class: The request class to resolve

       Returns:
           Handler instance for the request

       Raises:
           ValueError: If no handler is registered
       """
   ```

3. **Tests**: New features require tests with 100% coverage
   - Use function-based tests (pytest style)
   - Test both success and error cases
   - Use dataclasses for request/response types in tests

4. **Configuration**: Keep config files separate
   - pytest.ini for pytest config
   - mypy.ini for mypy config
   - ruff.toml for ruff config
   - pyproject.toml only for project metadata

### Understanding the Codebase

When contributing, start by reading these files in order:

1. **[registry.py](src/pymediate/registry.py)** - Understand the global registries
2. **[request.py](src/pymediate/request.py)** - See how requests register their response types
3. **[handler.py](src/pymediate/handler.py)** - The most complex module; understand metaclass magic
4. **[resolver.py](src/pymediate/resolver.py)** - Simple protocol and implementation
5. **[mediator.py](src/pymediate/mediator.py)** - Simple orchestration
6. **[di_resolver.py](src/pymediate/di_resolver.py)** - Optional DI integration

Key test files to understand patterns:
- **[test_handler.py](tests/test_handler.py)** - Handler validation tests
- **[test_dataclass_support.py](tests/test_dataclass_support.py)** - Real-world usage patterns
- **[test_di_resolver.py](tests/test_di_resolver.py)** - DI container integration

### Common Extension Points

#### Adding a New Resolver

1. Create a new file: `src/pymediate/my_resolver.py`
2. Implement the `Resolver` protocol:
   ```python
   from pymediate.handler import Handler
   from pymediate.resolver import Resolver

   class MyResolver:
       def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
           # Your resolution logic
           ...
   ```
3. Add tests in `tests/test_my_resolver.py`
4. Export from `__init__.py` if part of public API

#### Adding Validation Pipeline

```python
class ValidatingMediator(Mediator):
    def send(self, request: RequestType) -> Any:
        # Validate request
        if hasattr(request, 'validate'):
            request.validate()

        return super().send(request)
```

#### Adding Async Support (Future)

Currently being considered:
```python
class AsyncMediator:
    async def send(self, request: RequestType) -> Any:
        handler = self._resolver.resolve(type(request))
        if inspect.iscoroutinefunction(handler):
            return await handler(request)
        return handler(request)
```

### Debugging Tips

#### Type Inference Not Working?

Check `__orig_bases__`:
```python
class MyHandler(Handler[MyRequest]):
    pass

print(MyHandler.__orig_bases__)  # Should include Handler[MyRequest]
print(MyHandler._request_type)   # Should be MyRequest
print(MyHandler._response_type)  # Should be MyResponse
```

#### Handler Validation Failing?

Check the signature:
```python
import inspect

sig = inspect.signature(MyHandler.__call__)
print(sig.parameters)    # Check parameter types
print(sig.return_annotation)  # Check return type
```

#### Request Not Registered?

```python
from pymediate.registry import _REQUEST_REGISTRY

print(_REQUEST_REGISTRY)  # Should contain MyRequest -> MyResponse
```

---

## Future Direction

### Short-term Roadmap (v0.2.0)

1. **Async/Await Support**
   - `AsyncMediator` for async handlers
   - Mixed sync/async handler resolution
   - Proper type hints for async handlers

2. **Pipeline/Middleware System**
   - Pre-processing pipelines (validation, logging)
   - Post-processing pipelines (caching, transformation)
   - Configurable pipeline composition

3. **Streaming Responses**
   - Support for generators/async generators
   - Streaming large datasets
   - Progress reporting

### Medium-term Roadmap (v0.3.0)

1. **Notification Pattern**
   - `mediator.publish(notification)` for one-to-many
   - Multiple handlers per notification
   - Async notification handling

2. **Built-in Behaviors**
   - Retry behavior
   - Circuit breaker
   - Rate limiting
   - Caching

3. **Enhanced DI Support**
   - Support for more DI containers (injector, punq, etc.)
   - Auto-registration of handlers
   - Lifetime scope management

### Long-term Vision (v1.0.0)

1. **GraphQL/REST Integration**
   - Automatic endpoint generation from requests
   - OpenAPI schema generation
   - Request validation from schemas

2. **Observability**
   - Built-in metrics (request count, latency, errors)
   - Tracing integration (OpenTelemetry)
   - Structured logging

3. **Code Generation**
   - CLI tool to generate request/handler boilerplate
   - Type stub generation
   - Documentation generation

### Design Philosophy Going Forward

As PyMediate evolves, we commit to:

1. **Backward Compatibility**: No breaking changes without major version bump
2. **Zero-Config Default**: New features opt-in, core stays simple
3. **Type Safety First**: If it can't be type-checked, it shouldn't be in core
4. **Documentation Quality**: Every feature documented with examples
5. **Performance**: No feature that significantly impacts performance in core

### Community Contributions

We especially welcome contributions in these areas:

- **Resolver Implementations**: Support for different DI containers
- **Real-World Examples**: Production usage patterns and case studies
- **Performance Benchmarks**: Profiling and optimization
- **Documentation**: Tutorials, guides, and API documentation
- **Tooling**: IDE plugins, code generators, linters

---

## Conclusion

PyMediate represents a careful balance between Python's dynamic nature and modern type safety requirements. By leveraging metaclasses, protocols, and generic types, it provides a developer experience comparable to statically-typed languages while remaining idiomatic Python.

The project is built on the principle that **type safety should enhance, not hinder, developer productivity**. Every design decision prioritizes:
- Clear, actionable error messages over silent failures
- Automatic inference over manual configuration
- Extensibility through protocols over rigid hierarchies
- Real-world usability over theoretical purity

Whether you're building a small web service or a large enterprise application, PyMediate scales with your needs—from simple dict-based resolution to sophisticated dependency injection containers.

We invite you to use PyMediate, contribute to it, and help shape its future. The mediator pattern has proven valuable in many ecosystems; with PyMediate, it's now a first-class pattern in Python with full type safety.

---

## Quick Reference

### Installation

```bash
# Core only
pip install pymediate

# With dependency-injector support
pip install pymediate[di]

# Development
pip install -e ".[dev,di]"
```

### Minimal Example

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

@dataclass
class GreetingResponse:
    message: str

class GreetRequest(Request, response_type=GreetingResponse):
    def __init__(self, name: str):
        self.name = name

class GreetHandler(Handler[GreetRequest]):
    def __call__(self, request: GreetRequest) -> GreetingResponse:
        return GreetingResponse(message=f"Hello, {request.name}!")

resolver = SimpleResolver()
resolver.register(GreetRequest, GreetHandler())
mediator = Mediator(resolver)

response = mediator.send(GreetRequest("World"))
print(response.message)  # "Hello, World!"
```

### Testing Example

```python
def test_greet_handler():
    handler = GreetHandler()
    request = GreetRequest("Alice")
    response = handler(request)
    assert response.message == "Hello, Alice!"
```

### Key Files Reference

- **Core Logic**: [src/pymediate/handler.py](src/pymediate/handler.py:1-150)
- **Registry**: [src/pymediate/registry.py](src/pymediate/registry.py:1-50)
- **Request Base**: [src/pymediate/request.py](src/pymediate/request.py:1-100)
- **Mediator**: [src/pymediate/mediator.py](src/pymediate/mediator.py:1-50)
- **DI Integration**: [src/pymediate/di_resolver.py](src/pymediate/di_resolver.py:1-150)

---

**Last Updated**: 2025-01-18
**Version**: 0.1.0
**Authors**: PyMediate Contributors
**License**: MIT
