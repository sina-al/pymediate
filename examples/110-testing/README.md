# 110-testing

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F110-testing%2Fdevcontainer.json)

PyMediate handlers receive dependencies in `__init__` and handle requests in `__call__`.
Most handler tests can therefore construct and call a handler directly. Use a real mediator
only when the test needs to verify registration and composition.

This example covers three test boundaries and one registration rule that affects test design.
It assumes the constructor injection and mediator wiring used in
[100-dependency-injection](../100-dependency-injection/).

## Run

Run these commands from `examples/110-testing`:

```bash
uv sync
uv run pytest
```

```text
10 passed
```

## Direct handler test

Construct the handler with the dependency needed by the test, then call it:

```python
async def test_get_user_handler_returns_the_stored_user() -> None:
    repository = UserRepository()
    repository.create(username="alice", email="alice@example.com")
    handler = GetUserHandler(repository)

    user = await handler(GetUser(user_id=1))

    assert user.username == "alice"
```

This test does not need `Services` or `Mediator`. `pytest-asyncio` supplies the event-loop
support required by the asynchronous call.

## Three test boundaries

1. **Call a handler directly.** Use this for a handler's return value, errors, and direct
   dependency interactions. See [`test_handlers.py`](test_handlers.py).
2. **Replace the injected sender.** `RegisterUserHandler` dispatches
   `SendWelcomeEmail` through a narrow `Sender` protocol. A recording implementation verifies
   that request without configuring another handler. See
   [`test_composition.py`](test_composition.py).
3. **Send through a configured mediator.** Use this to verify that request types, handler
   instances, and collaborating handlers are registered together. See
   [`test_integration.py`](test_integration.py).

The second boundary looks like this:

```python
async def test_register_user_dispatches_a_welcome_email() -> None:
    sender = FakeSender()
    handler = RegisterUserHandler(sender, UserRepository())

    await handler(RegisterUser(username="alice", email="alice@example.com"))

    assert isinstance(sender.sent[0], SendWelcomeEmail)
```

`RegisterUserHandler` depends on the `Sender` protocol instead of the concrete `Mediator`.
Production wiring can supply a mediator-backed sender, while this test supplies a recording
implementation.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Compare the leaf handlers, the composing handler's `Sender` dependency, and `build_mediator`. |
| [`test_handlers.py`](test_handlers.py) | Call handlers directly with controlled dependencies. |
| [`test_composition.py`](test_composition.py) | Replace the injected sender and inspect the request it records. |
| [`test_integration.py`](test_integration.py) | Send through a configured mediator to verify registration and composition. |
| [`test_registry_gotcha.py`](test_registry_gotcha.py) | Verify process-global registration and constructor-based variation. |

## Details

### Handler registration is process-global

A `RequestHandler[RequestType]` subclass registers for its request type when Python executes
the class body. That registry is shared by the process, not created for each test or each
`Services` instance. Defining another handler class for the same request type raises
`HandlerAlreadyRegisteredError` at the class statement:

```python
def test_redefining_the_handler_class_raises() -> None:
    with pytest.raises(HandlerAlreadyRegisteredError, match="Greet"):

        class AnotherGreetHandler(RequestHandler[Greet]):
            async def __call__(self, request: Greet) -> GreetResponse:
                return GreetResponse(message=f"Bonjour, {request.name}!")
```

Define the handler class once. If tests need different behavior, pass dependencies or
configuration to separate instances:

```python
formal = GreetHandler(greeting="Good day")
casual = GreetHandler(greeting="Hey")
```

Event handlers have a related rule: several handler classes may subscribe to one event, so
test-local subclasses accumulate as subscriptions instead of raising a duplicate-registration
error. Define event-handler classes once and inject recordings or configuration into their
instances. If several classes are registered for the same event, all of them remain
subscribers.

## Where next

- [130-cqrs](../130-cqrs/) — separate command and query models and project writes into a
  read store. This example uses the asynchronous API.
- [110-testing-sync](../110-testing-sync/) — use the same test boundaries with
  `pymediate.sync`.
- [100-dependency-injection](../100-dependency-injection/) — review constructor injection and
  mediator wiring.
- Read the [testing guide](https://pymediate.sina-al.uk/docs/guide/testing).
