# Testing

PyMediate's framework independence (see [Requests and responses](../guide/requests-responses.md)) is what makes testing straightforward: handlers are plain callables with injected dependencies, so most of your tests never need a mediator, a web framework, or a database at all.

## Testing handlers directly

The fastest and most common test: construct the handler with fakes, call it, assert on the response. No mediator required.

```python
from dataclasses import dataclass
from pymediate import Request, Handler

@dataclass
class CreateUserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database):
        self.database = database

    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)

def test_create_user_handler():
    handler = CreateUserHandler(database=FakeDatabase())

    response = handler(CreateUserRequest(username="alice", email="alice@example.com"))

    assert response.username == "alice"
    assert response.user_id > 0
```

Prefer a fake or in-memory implementation over a mock for the dependency where it's practical — it exercises more real behavior for about the same amount of test code, and it's what [Basic usage](../examples/basic.md) uses.

## Testing through the mediator

Reserve this for the handful of tests that specifically verify request routing, [pipeline behavior](../guide/pipeline-behaviors.md) wiring, or handler composition through the mediator — not as a replacement for direct handler tests.

```python
from pymediate import Mediator, Services

def test_create_user_through_mediator():
    services = Services()
    services.add(CreateUserHandler(database=FakeDatabase()))
    mediator = Mediator(services.provider())

    response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))

    assert response.username == "alice"
```

## Mocking the mediator

When testing a handler that itself calls other handlers through an injected mediator (see [Handler composition](../guide/handlers.md#handler-composition)), fake the mediator rather than wiring up every handler it might call.

```python
class FakeMediator:
    def __init__(self):
        self.sent = []

    def send(self, request):
        self.sent.append(request)
        return FakeResponseFor(request)

def test_place_order_sends_expected_requests():
    mediator = FakeMediator()
    handler = PlaceOrderHandler(mediator=mediator, database=FakeDatabase())

    handler(PlaceOrderRequest(...))

    assert isinstance(mediator.sent[0], ChargePaymentRequest)
    assert isinstance(mediator.sent[1], SendEmailRequest)
```

## Testing async handlers

Async handlers are `async def __call__` methods, so test them with [pytest](https://docs.pytest.org/)'s `pytest.mark.asyncio` like any other coroutine — direct calls and mediator calls both work the same way as the sync case.

```python
import pytest
from pymediate import Services
from pymediate.aio import Mediator

@pytest.mark.asyncio
async def test_async_handler_directly():
    handler = FetchDataHandler(http_client=FakeHttpClient())

    response = await handler(FetchDataRequest(url="https://api.example.com/data"))

    assert response.data is not None

@pytest.mark.asyncio
async def test_async_handler_through_mediator():
    services = Services()
    services.add(FetchDataHandler(http_client=FakeHttpClient()))
    mediator = Mediator(services.provider())

    response = await mediator.send(FetchDataRequest(url="https://api.example.com/data"))

    assert response.data is not None
```

Note that `Services` itself is imported from `pymediate`, not `pymediate.aio`, even in async tests — only `Handler` and `Mediator` have separate sync/async variants. See [Async/await support](../examples/async.md).

## A test-isolation gotcha: the handler registry is global

Each `Handler[RequestT]` subclass registers itself against its request type the moment the class body executes — not per `Services` instance, but in a single registry shared by the whole process. Defining a second `Handler` for a request type that already has one raises `HandlerAlreadyRegisteredError`, and that applies just as much across two test functions as it does in application code.

```python
# test_a.py
class TempHandler(Handler[SharedRequest]):
    def __call__(self, request: SharedRequest) -> SharedResponse:
        return SharedResponse(value=1)

# test_b.py - if SharedRequest is the same class, this collides at import/collection time
class TempHandler(Handler[SharedRequest]):
    def __call__(self, request: SharedRequest) -> SharedResponse:
        return SharedResponse(value=2)
# HandlerAlreadyRegisteredError: Handler already registered for 'SharedRequest'
```

Vary behavior through the constructor instead of redefining the class.

```python
class ConfigurableHandler(Handler[SharedRequest]):
    def __init__(self, value: int):
        self.value = value

    def __call__(self, request: SharedRequest) -> SharedResponse:
        return SharedResponse(value=self.value)

# test_a.py
handler = ConfigurableHandler(value=1)
# test_b.py
handler = ConfigurableHandler(value=2)
```

If you genuinely need two distinct handler implementations, give them distinct request types instead — see [Troubleshooting: HandlerAlreadyRegisteredError](troubleshooting.md#handleralreadyregisterederror) for the full set of options.

## Fixtures and organization

Ordinary pytest fixtures work well for the pieces you construct repeatedly — a fake database, a populated request, a wired-up mediator.

```python
import pytest

@pytest.fixture
def fake_database():
    return FakeDatabase()

@pytest.fixture
def create_user_handler(fake_database):
    return CreateUserHandler(database=fake_database)

def test_create_user(create_user_handler):
    response = create_user_handler(
        CreateUserRequest(username="alice", email="alice@example.com")
    )
    assert response.user_id > 0
```

This project's own test suite (`tests/`) enforces a 95% coverage floor and organizes tests by concern — one file per `Handler`, `Mediator`, `Services`, and pipeline behaviors, plus a separate `tests/mypy/` suite for the library's static-typing guarantees (see [Type safety](type-safety.md#how-this-project-tests-its-own-type-safety)). The same shape works well for application code: keep handler tests next to the handlers they cover, and keep the smaller set of mediator/pipeline integration tests separate from them.

## Next steps

- [Error handling](../guide/error-handling.md) - Domain vs. framework errors and where to map them.
- [Type safety](type-safety.md) - What mypy catches vs. what's validated at runtime.
- [Troubleshooting](troubleshooting.md) - Common registration and configuration mistakes.
