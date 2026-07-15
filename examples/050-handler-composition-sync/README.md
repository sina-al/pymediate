# 050-handler-composition-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition-sync%2Fdevcontainer.json)

The synchronous mirror of [050-handler-composition](../050-handler-composition/), on
`pymediate.sync`. Same revelation: a handler that needs another operation done
**dispatches a request through the mediator** instead of holding the other handler. The one
visible difference is that with no event loop, the sub-requests run **one after another**.

## Run it

```bash
cd examples/050-handler-composition-sync
uv sync
uv run orders
```

```text
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

Diff this journal against the async twin's. There, `charge:start` appears *before*
`reserve:done` — the two sub-requests overlap. Here, `reserve:done` comes first: the sync
mediator runs each `send` to completion before the next begins. The composition pattern is
identical; only the concurrency differs.

## The money shot: a handler that dispatches

`PlaceOrderHandler` owns exactly one thing — placing an order. Everything else it needs, it
asks the mediator for:

```python
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender                       # the mediator's dispatch interface

    def __call__(self, request: PlaceOrder) -> Order:
        reservation = self._sender.send(ReserveStock(request.sku, request.quantity))
        receipt = self._sender.send(ChargePayment(request.customer_id, request.amount_cents))
        order = Order(next(self._next_id), reservation, receipt)
        self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        return order
```

No import of `ReserveStockHandler`, no reference to `ChargePaymentHandler` — this handler
doesn't know they exist. It sends `ReserveStock` and `ChargePayment` and lets the mediator
find whoever handles them. (The async twin wraps the two `send` calls in `asyncio.gather` to
overlap them; sync runs them in sequence.)

## Closing the construction cycle

The composing handler needs something to dispatch on — but the mediator is built *from* the
handlers, so it doesn't exist yet when the handler is constructed. The handler depends on a
narrow `Sender` interface, and we register a `LateBoundSender` we `bind` once the mediator
exists:

```python
sender = LateBoundSender()
services.add(PlaceOrderHandler(sender, journal))   # depends on the sender, not the mediator
# ...register the other handlers...
mediator = Mediator(services.provider())
sender.bind(mediator)                              # close the loop
```

## The files

| File | What it is |
| --- | --- |
| [`src/orders/handlers.py`](src/orders/handlers.py) | **Start here.** The two sub-handlers, the composing `PlaceOrderHandler`, and two event subscribers. |
| [`src/orders/domain.py`](src/orders/domain.py) | Value objects, requests, the `OrderPlaced` event, fake warehouse/gateway, and the `Sender`/`LateBoundSender` seam. |
| [`src/orders/app.py`](src/orders/app.py) | `build_mediator` (where the cycle is closed) and the demo. |
| [`tests/test_composition.py`](tests/test_composition.py) | Asserts the sub-requests ran, that they ran sequentially, and that a failing sub-request propagates: `uv run pytest` → `4 passed`. |

## Where next

- [050-handler-composition](../050-handler-composition/) — the async original, where the two
  sub-requests overlap via `asyncio.gather`.
- [060-messages](../060-messages/) — model requests as immutable, self-validating value objects.
- The docs: [handlers guide](https://pymediate.sina-al.uk/docs/guide/handlers).
