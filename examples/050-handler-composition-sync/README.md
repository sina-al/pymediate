# 050-handler-composition-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition-sync%2Fdevcontainer.json)

The synchronous mirror of [050-handler-composition](../050-handler-composition/), on
`pymediate.sync` — no event loop. One operation often needs others: placing an order means
reserving stock *and* quoting shipping first. How do you make one handler trigger those
without wiring the handlers together into a tangle? You don't wire them at all — a handler
that needs another operation just `send()`s a request through the mediator, exactly like
your outermost caller does. Sync has no concurrency, so the sub-requests run one after
another.

## Run it

```bash
cd examples/050-handler-composition-sync
uv sync
uv run taskboard
```

```text
Placed order 1: reservation=resv-1, shipping=10
Sub-request timeline (sequential — each finishes before the next starts):
  reserve:start
  reserve:done
  quote:start
  quote:done
```

`reserve` finishes completely before `quote` starts — the sync mediator runs them in
order. Placing one order dispatched two more, and no handler holds a reference to another.
(Diff this against the [async twin](../050-handler-composition/), where the same two
sub-requests overlap.)

## The money shot: a handler that dispatches

```python
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, dispatch: Dispatcher, store: OrderStore) -> None:
        self._dispatch = dispatch          # a send-capable handle, not other handlers
        self._store = store

    def __call__(self, request: PlaceOrder) -> Order:
        reservation = self._dispatch.send(ReserveStock(items=request.items))
        quote = self._dispatch.send(QuoteShipping(items=request.items))
        return self._store.save(
            items=request.items,
            reservation_id=reservation.reservation_id,
            shipping_cost=quote.cost,
        )
```

`PlaceOrderHandler` never imports `ReserveStockHandler` or `QuoteShippingHandler`. It sends
two requests; the mediator resolves and runs the handler for each. A handler is just a
caller like any other. (The async twin runs these two with `asyncio.gather`; here they're
sequential — that's the only real difference.)

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
| [`src/taskboard/operations.py`](src/taskboard/operations.py) | **Start here.** The two leaf handlers and `PlaceOrderHandler`, which composes them. |
| [`src/taskboard/dispatch.py`](src/taskboard/dispatch.py) | `Dispatcher` — the late-bound send handle that breaks the construction cycle. |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | `Order`, the fake warehouse/rates/store, and the traces the demo and tests read. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | `build_mediator` (the wiring order that matters) and the demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | Asserts both sub-requests ran, the result is assembled from both, and they ran in order: `uv run pytest` → `4 passed`. |

## Small print

- The sub-requests are ordinary `Request`s, not private helpers — anything can `send` a
  `ReserveStock`. Composition adds a caller; it doesn't hide the operation (a test proves
  it).
- The [async twin](../050-handler-composition/) overlaps the two independent sub-requests
  with `asyncio.gather`; here they're sequential because there's no event loop. The
  composition shape is identical — only the delivery differs.
- A composing handler could just as well `publish()` an event to announce what happened
  (the "many reactors" half); that's the [020-events-sync](../020-events-sync/) lesson.
  This example stays on request→response composition.

## Where next

- [050-handler-composition](../050-handler-composition/) — the async default this mirrors,
  where the two sub-requests overlap via `asyncio.gather`.
- [020-events-sync](../020-events-sync/) — the other way one operation reaches many:
  `publish()` fan-out.
- The docs: [handlers guide](https://pymediate.sina-al.uk/docs/guide/handlers).
