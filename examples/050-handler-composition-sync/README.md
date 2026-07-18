# 050-handler-composition-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F050-handler-composition-sync%2Fdevcontainer.json)

`PlaceOrderHandler` reserves stock, charges a card, and publishes `OrderPlaced` by dispatching
through a synchronous mediator. It depends on request and event types rather than concrete
handler classes.

## Run

From this directory:

```bash
uv sync
uv run pytest
```

```text
4 passed
```

Run the console example to see the execution order:

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

Each `send` completes before the next begins. `publish` then calls every subscriber in
registration order and returns after all of them finish.

## Compose through the mediator

```python
class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender
        self._journal = journal
        self._next_id = count(1)

    def __call__(self, request: PlaceOrder) -> Order:
        reservation = self._sender.send(ReserveStock(request.sku, request.quantity))
        receipt = self._sender.send(
            ChargePayment(request.customer_id, request.amount_cents)
        )
        order = Order(next(self._next_id), reservation, receipt)
        self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        return order
```

The reservation and payment handlers do not know that `PlaceOrderHandler` uses them. Mediator
dispatch also applies any behaviors registered for the subrequest types. The cost is indirect
control flow: a reader must follow each request type to find its handler.

Direct service or subhandler injection is also valid. It makes calls explicit and can simplify
construction, but the composing handler then depends on those service interfaces and direct
calls do not enter mediator pipelines automatically.

## Bind the sender

The mediator is created from its handlers, while `PlaceOrderHandler` needs a sender that will
eventually forward to that mediator. `LateBoundSender` allows registration before the mediator
exists and is bound immediately afterward.

```python
sender = LateBoundSender()
services.add(PlaceOrderHandler(sender, journal))
mediator = Mediator(services.provider())
sender.bind(mediator)
```

`Sender` is a narrow `Protocol` containing `send` and `publish`. `Mediator` satisfies it, and a
test double can implement the same two methods.

## Read the code

| File | What to read |
| --- | --- |
| [`src/orders/handlers.py`](src/orders/handlers.py) | Start here for the composing handler, subrequest handlers, and subscribers. |
| [`src/orders/domain.py`](src/orders/domain.py) | Requests, results, service doubles, and the `Sender` protocol. |
| [`src/orders/app.py`](src/orders/app.py) | Service registration and late binding. |
| [`tests/test_composition.py`](tests/test_composition.py) | Dispatch order, subscriber delivery, and partial failure effects. |

## Details

Sequential calls are not automatically transactional. An out-of-stock error occurs before the
payment call, so no charge is made. If payment is declined, however, the earlier reservation
remains. The tests assert both outcomes.

Production order processing must define failure handling. Depending on the storage and external
services, that can mean deliberate ordering, idempotency keys, a database transaction, or a
compensating action. Publishing returns after every subscriber finishes.

## Where next

- [060-messages-sync](../060-messages-sync/) explains how request data affects equality,
  representation, and validation.
- [050-handler-composition](../050-handler-composition/) shows concurrent subrequests with the
  asynchronous API.
- Read the [core concepts guide](https://pymediate.sina-al.uk/docs/getting-started/concepts).
