# 110-testing-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F110-testing-sync%2Fdevcontainer.json)

The synchronous mirror of [110-testing](../110-testing/), on `pymediate.sync`. Same
three layers of test (direct handler, faked mediator, real mediator), the same
process-global registry gotcha, and no `pytest-asyncio` needed at all — every test is
a plain `def`.

## Run it

```bash
cd examples/110-testing-sync
uv sync
uv run pytest
```

```text
10 passed
```

## What changes from the async version

Only the API import and the mechanics — every claim under test is identical:

```python
# app.py
from pymediate.sync import Mediator, Request, RequestHandler, Services

class GetUserHandler(RequestHandler[GetUser]):
    def __call__(self, request: GetUser) -> User:      # no async
        ...

# test_handlers.py
def test_get_user_handler_returns_the_stored_user() -> None:   # no async, no await
    handler = GetUserHandler(repository)
    user = handler(GetUser(user_id=1))
    assert user.username == "alice"
```

Every handler, fake, and test in this example is byte-for-byte the same shape as the
async twin, minus `async`/`await` — including the registry gotcha:
`HandlerAlreadyRegisteredError` fires at the same `class` statement, sync or async.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The application under test: `GetUserHandler` (a leaf), `RegisterUserHandler` (composes through a `Sender`), `GreetHandler` (constructor-configurable). |
| [`test_handlers.py`](test_handlers.py) | Layer 1: direct handler tests, no mediator. |
| [`test_composition.py`](test_composition.py) | Layer 2: `FakeSender` stands in for the mediator. |
| [`test_integration.py`](test_integration.py) | Layer 3: a real `Mediator`, both handlers wired together. |
| [`test_registry_gotcha.py`](test_registry_gotcha.py) | The pitfall and the fix, demonstrated: `uv run pytest` → `10 passed` across all four files. |

## Where next

- [110-testing](../110-testing/) — the async default, with the full explanation of
  all three layers and the registry gotcha.
- [050-handler-composition-sync](../050-handler-composition-sync/) — where `Sender`
  and `LateBoundSender` come from, on `pymediate.sync`.
- The docs: [testing guide](https://pymediate.sina-al.uk/docs/advanced/testing).
