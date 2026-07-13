# 050-handler-composition

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition%2Fdevcontainer.json)

One operation often needs others: placing an order means reserving stock *and* quoting
shipping first. How do you make one handler trigger those without wiring the handlers
together into a tangle? You don't wire them at all — a handler that needs another operation
just `send()`s a request through the mediator, exactly like your outermost caller does. And
because independent sub-requests don't depend on each other, you can run them concurrently.

## Run it

```bash
cd examples/050-handler-composition
uv sync
uv run taskboard
```

```text
Placed order 1: reservation=resv-1, shipping=10
Sub-request timeline (both start before either finishes):
  reserve:start
  quote:start
  reserve:done
  quote:done
```

`reserve` and `quote` both **start** before either **finishes** — the two sub-requests
overlapped. Placing one order dispatched two more, concurrently, and no handler holds a
reference to another.

## The money shot: a handler that dispatches, and overlaps

```python
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, dispatch: Dispatcher, store: OrderStore) -> None:
        self._dispatch = dispatch          # a send-capable handle, not other handlers
        self._store = store

    async def __call__(self, request: PlaceOrder) -> Order:
        reservation, quote = await asyncio.gather(
            self._dispatch.send(ReserveStock(items=request.items)),
            self._dispatch.send(QuoteShipping(items=request.items)),
        )
        return self._store.save(
            items=request.items,
            reservation_id=reservation.reservation_id,
            shipping_cost=quote.cost,
        )
```

`PlaceOrderHandler` never imports `ReserveStockHandler` or `QuoteShippingHandler`. It sends
two requests; the mediator resolves and runs the handler for each. The two are independent,
so `asyncio.gather` runs them together — the order is saved only once both return. A
handler is just a caller like any other.

## The wiring: breaking the construction cycle

The orchestrator needs the mediator to send through. But the mediator can't be built until
every handler — the orchestrator included — is registered. That's a cycle:
provider → orchestrator → mediator → provider.

The fix is a small late-bound handle. The orchestrator is injected with a `Dispatcher` at
construction; `build_mediator` fills in the real mediator as its **last** step:

```python
dispatch = Dispatcher()                       # constructed empty
services = Services()
services.add(ReserveStockHandler(warehouse))
services.add(QuoteShippingHandler(rates))
services.add(PlaceOrderHandler(dispatch, store))
mediator = Mediator(services.provider())
dispatch.bind(mediator)                        # now the orchestrator can send()
```

`Dispatcher.send` has the same typed signature as `Mediator.send`, so the orchestrator
depends on "something I can send through" — not on how it was wired, and never on another
handler.

## The files

| File | What it is |
| --- | --- |
| [`src/taskboard/operations.py`](src/taskboard/operations.py) | **Start here.** The two leaf handlers and `PlaceOrderHandler`, which composes them via `gather`. |
| [`src/taskboard/dispatch.py`](src/taskboard/dispatch.py) | `Dispatcher` — the late-bound send handle that breaks the construction cycle. |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | `Order`, the fake warehouse/rates/store, and the traces the demo and tests read. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | `build_mediator` (the wiring order that matters) and the demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | Asserts both sub-requests ran, the result is assembled from both, and they overlapped: `uv run pytest` → `4 passed`. |

## Small print

- The sub-requests are ordinary `Request`s, not private helpers — anything can `send` a
  `ReserveStock`. Composition adds a caller; it doesn't hide the operation (a test proves
  it).
- Prefer `gather` only for sub-requests that are genuinely independent. If one needs the
  other's result, `await` them in sequence — the composition shape is the same, just not
  overlapped.
- A composing handler could just as well `publish()` an event to announce what happened
  (the "many reactors" half); that's the [020-events](../020-events/) lesson. This example
  stays on request→response composition.

## Where next

- [050-handler-composition-sync](../050-handler-composition-sync/) — the same composition
  on `pymediate.sync`, where the two sub-requests run sequentially (no event loop).
- [020-events](../020-events/) — the other way one operation reaches many: `publish()`
  fan-out.
- The docs: [handlers guide](https://pymediate.sina-al.uk/docs/guide/handlers).
