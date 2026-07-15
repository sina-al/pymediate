# 050-handler-composition

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition%2Fdevcontainer.json)

How does one operation trigger others — reserve stock, charge a card, send a confirmation —
*without* wiring the handlers together into a tangle? In PyMediate a handler that needs
another operation done doesn't hold that handler; it **dispatches a request through the
mediator**. Each command keeps a single owner, and independent sub-requests run
**concurrently** with `asyncio.gather`. This example is a `PlaceOrder` handler that
orchestrates three others and touches none of them directly.

## Run it

```bash
cd examples/050-handler-composition
uv sync
uv run orders
```

```text
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

Read the journal top to bottom. Both sub-requests **start** (`reserve:start`,
`charge:start`) before either **finishes** — that overlap is `gather` running them at the
same time, not one after another. Then the order is announced, and two subscribers react.

## The money shot: a handler that dispatches

`PlaceOrderHandler` owns exactly one thing — placing an order. Everything else it needs, it
asks the mediator for:

```python
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender                       # the mediator's dispatch interface

    async def __call__(self, request: PlaceOrder) -> Order:
        # Independent sub-requests → run them at the same time.
        reservation, receipt = await asyncio.gather(
            self._sender.send(ReserveStock(request.sku, request.quantity)),
            self._sender.send(ChargePayment(request.customer_id, request.amount_cents)),
        )
        order = Order(next(self._next_id), reservation, receipt)
        await self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        return order
```

No import of `ReserveStockHandler`, no reference to `ChargePaymentHandler` — this handler
doesn't know they exist. It sends `ReserveStock` and `ChargePayment` and lets the mediator
find whoever handles them. Swap either handler out and this code doesn't change. Because
reserving stock and charging a card are independent, `gather` runs both concurrently and
hands back their results in order.

## Closing the construction cycle

There's one wrinkle worth naming. The composing handler needs something to dispatch on —
but the mediator is built *from* the handlers, so it doesn't exist yet when the handler is
constructed. Injecting the `Mediator` directly would be chicken-and-egg.

The fix is a small seam. The handler depends on a narrow `Sender` interface (just `send`
and `publish`), and we register a `LateBoundSender` — a stand-in you `bind` once the
mediator exists:

```python
sender = LateBoundSender()
services.add(PlaceOrderHandler(sender, journal))   # depends on the sender, not the mediator
# ...register the other handlers...
mediator = Mediator(services.provider())
sender.bind(mediator)                              # close the loop
```

Two extra lines, and the cycle is gone. Depending on the `Sender` interface rather than the
concrete `Mediator` also makes the handler trivial to test with a fake dispatcher.

## The files

| File | What it is |
| --- | --- |
| [`src/orders/handlers.py`](src/orders/handlers.py) | **Start here.** The two sub-handlers, the composing `PlaceOrderHandler`, and two event subscribers. |
| [`src/orders/domain.py`](src/orders/domain.py) | Value objects, requests, the `OrderPlaced` event, fake warehouse/gateway, and the `Sender`/`LateBoundSender` seam. |
| [`src/orders/app.py`](src/orders/app.py) | `build_mediator` (where the cycle is closed) and the demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | Asserts the sub-requests ran, that they overlapped, and that a failing sub-request propagates: `uv run pytest` → `4 passed`. |

## Small print

- **One revelation: composition through the mediator.** The `OrderPlaced` event is the
  "announce" side of the same idea — if events are new to you, see [020-events](../020-events/).
- If a sub-request fails (out of stock, card declined), the exception propagates straight
  out of `send(PlaceOrder)` and the order is never announced. `gather` surfaces the first
  failure; coordinating rollback across sub-requests (the saga problem) is its own topic.
- The warehouse and payment gateway are deliberately fake, in-process stand-ins. Real
  services drop in behind the same handlers without touching `PlaceOrderHandler`.

## Where next

- [050-handler-composition-sync](../050-handler-composition-sync/) — the same composition on
  `pymediate.sync`, where the sub-requests run **sequentially** (no event loop to overlap on).
- [060-messages](../060-messages/) — model requests as immutable, self-validating value objects.
- The docs: [handlers guide](https://pymediate.sina-al.uk/docs/guide/handlers).
