# 050-handler-composition

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition%2Fdevcontainer.json)

One command, `PlaceOrder`, needs three things done — reserve stock, charge a card, announce
the result. The handler that owns it does none of them itself and **holds none of the other
handlers**: it dispatches sub-requests and an event back through the mediator, and runs the
two independent ones at the same time.

## Run it

```bash
cd examples/050-handler-composition
uv sync
uv run pytest
```

```text
4 passed
```

Then place an order and watch the order of execution:

```console
$ uv run orders
Placed order #1 for 2 x WIDGET, charged 1999c
Journal (top to bottom = order of execution):
  place:start
  reserve:start WIDGET
  charge:start cust-1
  reserve:done WIDGET
  charge:done cust-1
  email:sent cust-1
  analytics:recorded 1
  place:done
```

Both sub-requests **start** before either one finishes — `reserve:start` and `charge:start`
are back to back, ahead of either `:done`. They were in flight at the same time.

## The composing handler

```python
# handlers.py — owns one operation, holds no other handler, only the mediator's send/publish
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender          # the mediator's dispatch seam, not the sub-handlers
        self._next_id = count(1)

    async def __call__(self, request: PlaceOrder) -> Order:
        # Reserving stock and charging the card are independent — run them concurrently.
        reservation, receipt = await asyncio.gather(
            self._sender.send(ReserveStock(request.sku, request.quantity)),
            self._sender.send(ChargePayment(request.customer_id, request.amount_cents)),
        )
        order = Order(next(self._next_id), reservation, receipt)
        await self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        return order
```

`ReserveStockHandler` and `ChargePaymentHandler` are ordinary handlers, each unaware it's
being composed. `PlaceOrderHandler` reaches them the same way any caller would — two `send`
calls — then announces the finished order with one `publish`. It never imports or references
another handler, so the dependency graph stays flat. Because the two sub-requests don't
depend on each other, `asyncio.gather` overlaps them; swapping in `await`-one-then-the-other
would be the only change needed to serialize them.

## Closing the construction cycle

There's a chicken-and-egg problem hiding in that `Sender`. The mediator is built *from* the
handlers, so it doesn't exist yet when `PlaceOrderHandler` is constructed — you can't inject
the mediator the handler needs to dispatch into. The fix is to depend on a narrow interface,
not the concrete mediator, and bind it a moment later:

```python
# app.py — two extra lines close the loop
sender = LateBoundSender()                     # a Sender you can register before the mediator exists
services.add(PlaceOrderHandler(sender, journal))
...
mediator = Mediator(services.provider())
sender.bind(mediator)                          # now the handler dispatches into its own mediator
```

`Sender` is a two-method `Protocol` (`send`, `publish`) that `Mediator` already satisfies
structurally. Depending on *it* — rather than `Mediator` — is also what lets a test hand the
composing handler a fake and check what it dispatched, without a real mediator at all.

## The files

| File | What it is |
| --- | --- |
| [`src/orders/handlers.py`](src/orders/handlers.py) | **Start here.** The two leaf handlers, the composing `PlaceOrderHandler`, and the two event subscribers. |
| [`src/orders/domain.py`](src/orders/domain.py) | Value objects, the requests and event, the fakes, and the `Sender` / `LateBoundSender` seam. |
| [`src/orders/app.py`](src/orders/app.py) | Wiring: register the late-bound sender, build the mediator, `bind` it — plus the `uv run orders` demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | The four claims: sub-requests dispatched, event delivered, sub-requests overlap, a failure propagates. |

## Small print

- **Composing by dispatch, not by holding.** Injecting the sub-handlers into `PlaceOrder`
  directly would work, but it rebuilds the very tangle the mediator removed — the composing
  handler would know each collaborator's constructor and type. Dispatching keeps it knowing
  only the *requests*.
- **Announce and move on.** The two subscribers (`OrderConfirmation`, `SalesAnalytics`)
  react to `OrderPlaced` independently; the order handler names neither and depends on
  neither. That's the `publish` half of composition — see [020-events](../020-events/) for
  it on its own.
- **A failing sub-request propagates.** If `ReserveStock` raises `OutOfStockError`, it
  surfaces straight out of `send(PlaceOrder)` and the order is never announced — no partial
  `OrderPlaced`. The tests pin both the out-of-stock and declined-payment paths.

## Where next

- [050-handler-composition-sync](../050-handler-composition-sync/) — the same composition on
  `pymediate.sync`, where the sub-requests run sequentially. Diff the two journals.
- [020-events](../020-events/) — `publish()` on its own: one event, many independent subscribers.
- [040-pipeline-behaviors](../040-pipeline-behaviors/) — the other way to factor shared work,
  *around* a handler rather than *from inside* one.
- The docs: [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
