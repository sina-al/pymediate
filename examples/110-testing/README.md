# 110-testing

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F110-testing%2Fdevcontainer.json)

How do you test handlers without a patch tower? In PyMediate a handler is `__init__`
plus `__call__` — a plain callable with injected dependencies — so most tests never
need a mediator, a web framework, or a database at all. This example shows three
layers of test, cheapest first, and the one sharp edge: the handler registry is
**process-global**, so two tests can't each define their own version of the same
handler class.

## Run it

```bash
cd examples/110-testing
uv sync
uv run pytest
```

```text
10 passed
```

## The money shot: a handler is just a callable

```python
async def test_get_user_handler_returns_the_stored_user() -> None:
    repository = UserRepository()
    repository.create(username="alice", email="alice@example.com")
    handler = GetUserHandler(repository)          # construct it directly

    user = await handler(GetUser(user_id=1))      # call it directly — no mediator

    assert user.username == "alice"
```

No `Services`, no `Mediator`, no `pytest` plugin beyond `pytest-asyncio` for the
`await`. `GetUserHandler` takes a `UserRepository` in its constructor and returns a
`User` from `__call__` — testing it is testing any other Python object.

## Three layers, cheapest first

1. **Direct handler tests** ([`test_handlers.py`](test_handlers.py)) — construct with a
   fake dependency, call, assert. The fastest and most common test in the suite.
2. **Faking the mediator** ([`test_composition.py`](test_composition.py)) — for a
   handler that itself dispatches (`RegisterUserHandler` sends `SendWelcomeEmail`
   through an injected `Sender`), swap in a `FakeSender` that records what it was
   asked to send. Still no real mediator, no second handler wired up.
3. **Through a real `Mediator`** ([`test_integration.py`](test_integration.py)) — reserve
   this for what layers 1–2 structurally can't check: that the pieces are wired
   together correctly. It costs a container and two collaborating handlers to answer
   one question the cheaper layers each answer more cheaply on their own.

```python
# Layer 2: fake the sender, not the whole mediator
async def test_register_user_dispatches_a_welcome_email() -> None:
    sender = FakeSender()
    handler = RegisterUserHandler(sender, UserRepository())

    await handler(RegisterUser(username="alice", email="alice@example.com"))

    assert isinstance(sender.sent[0], SendWelcomeEmail)
```

## The sharp edge: the registry is process-global

Every `RequestHandler[RequestT]` subclass registers itself against its request type
the moment the class body executes — in **one registry shared by the whole process**,
not per test. Define a second handler for a request type that already has one, and it
raises `HandlerAlreadyRegisteredError`, right at the `class` statement:

```python
def test_redefining_the_handler_class_raises() -> None:
    with pytest.raises(HandlerAlreadyRegisteredError, match="Greet"):

        class AnotherGreetHandler(RequestHandler[Greet]):   # Greet already has GreetHandler
            async def __call__(self, request: Greet) -> GreetResponse:
                return GreetResponse(message=f"Bonjour, {request.name}!")
```

**The fix: vary the constructor, not the class.**

```python
formal = GreetHandler(greeting="Good day")
casual = GreetHandler(greeting="Hey")

assert (await formal(Greet(name="Alice"))).message == "Good day, Alice!"
assert (await casual(Greet(name="Bob"))).message == "Hey, Bob!"
```

Two tests wanting two different behaviors construct two instances of one class,
instead of each defining their own `RequestHandler[Greet]`. See
[`test_registry_gotcha.py`](test_registry_gotcha.py) for the full pair.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The application under test: `GetUserHandler` (a leaf), `RegisterUserHandler` (composes through a `Sender`), `GreetHandler` (constructor-configurable). |
| [`test_handlers.py`](test_handlers.py) | Layer 1: direct handler tests, no mediator. |
| [`test_composition.py`](test_composition.py) | Layer 2: `FakeSender` stands in for the mediator. |
| [`test_integration.py`](test_integration.py) | Layer 3: a real `Mediator`, both handlers wired together. |
| [`test_registry_gotcha.py`](test_registry_gotcha.py) | The pitfall and the fix, demonstrated: `uv run pytest` → `10 passed` across all four files. |

## Small print

- `event` handlers live in the same process-global registry with the *opposite*
  failure mode: any number may subscribe to one event, so there's no
  duplicate-registration error — subscriptions from every test file just accumulate.
  The fix is the same discipline: vary through constructors, not by redefining classes.
- Prefer a fake or in-memory implementation over a mock where practical — `FakeMailer`
  and `FakeSender` here exercise more real behavior for about the same test code.
- `RegisterUserHandler` depends on `Sender` (a narrow `Protocol`), not the concrete
  `Mediator` — that's what makes it fakeable in layer 2 without a real mediator.

## Where next

- [110-testing-sync](../110-testing-sync/) — the same three layers and the same
  gotcha on `pymediate.sync`.
- [050-handler-composition](../050-handler-composition/) — where `Sender` and
  `LateBoundSender` come from: a handler that dispatches sub-requests concurrently.
- The docs: [testing guide](https://pymediate.sina-al.uk/docs/advanced/testing).
