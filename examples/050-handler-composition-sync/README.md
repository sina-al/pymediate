# 050-handler-composition-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition-sync%2Fdevcontainer.json)

The synchronous mirror of [050-handler-composition](../050-handler-composition/), on
`pymediate.sync`. Same composition: `PlaceOrderHandler` owns one operation, holds no other
handler, and dispatches its sub-requests and event back through the mediator. The one visible
difference is that the two sub-requests run **one after another** — there's no event loop to
overlap them on.

## Run it

```bash
cd examples/050-handler-composition-sync
uv sync
uv run pytest
```

```text
4 passed
```

```console
$ uv run orders
Placed order #1 for 2 x WIDGET, charged 1999c
Journal (top to bottom = order of execution):
  place:start
  reserve:start WIDGET
  reserve:done WIDGET
  charge:start cust-1
  charge:done cust-1
  email:sent cust-1
  analytics:recorded 1
  place:done
```

Diff this journal against the async twin's: here `reserve:done` lands **before**
`charge:start` — the first `send` fully completes before the second begins.

## What changes from the async version

Only the mechanics. The composition — dispatch, don't hold — is identical; the sub-requests
just run in sequence instead of concurrently:

```python
# handlers.py
def __call__(self, request: PlaceOrder) -> Order:
    # Same two sub-requests as the async twin, but sequential: no event loop to overlap on,
    # so the first send fully completes before the second begins.
    reservation = self._sender.send(ReserveStock(request.sku, request.quantity))
    receipt = self._sender.send(ChargePayment(request.customer_id, request.amount_cents))
    order = Order(next(self._next_id), reservation, receipt)
    self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
    return order
```

Everything else mirrors the async twin minus `async`/`await`: `Sender` becomes a plain
`Protocol`, `LateBoundSender` forwards synchronously, and the [`app.py`](src/orders/app.py)
demo drops the `asyncio.run` wrapper. The construction-cycle fix — register a
`LateBoundSender`, build the mediator, `bind` it — is line-for-line the same.

## The files

| File | What it is |
| --- | --- |
| [`src/orders/handlers.py`](src/orders/handlers.py) | **Start here.** The two leaf handlers, the composing `PlaceOrderHandler`, and the two event subscribers. |
| [`src/orders/domain.py`](src/orders/domain.py) | Value objects, the requests and event, the fakes, and the `Sender` / `LateBoundSender` seam. |
| [`src/orders/app.py`](src/orders/app.py) | Wiring: register the late-bound sender, build the mediator, `bind` it — plus the `uv run orders` demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | The four claims: sub-requests dispatched, event delivered, sub-requests run in order, a failure propagates. |

## Where next

- [050-handler-composition](../050-handler-composition/) — the async default, with the full
  explanation of composing through the mediator and the construction-cycle fix.
- [020-events-sync](../020-events-sync/) — `publish()` on its own: one event, many independent
  subscribers, delivered sequentially.
- [040-pipeline-behaviors-sync](../040-pipeline-behaviors-sync/) — the other way to factor
  shared work, *around* a handler rather than *from inside* one.
- The docs: [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
