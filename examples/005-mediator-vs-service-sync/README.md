# 005-mediator-vs-service-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F005-mediator-vs-service-sync%2Fdevcontainer.json)

This optional orientation compares two synchronous implementations of the same orders
feature: one `OrderService` and one request handler per operation. Start with
[010-basic-sync](../010-basic-sync/) for the first synchronous implementation lesson.

## Run

From this example directory:

```bash
uv sync
uv run pytest
```

```text
8 passed
```

The tests demonstrate the runtime differences. The static typing differences described
below follow from the annotated signatures and are not runtime test assertions.

## Compare a service with request handlers

The first implementation puts every operation on `OrderService`. Its direct methods are
typed. It also includes an optional `dispatch(action, payload)` entry point to show what
happens when dynamic callers route operations by string:

```python
class OrderService:
    def __init__(self, store, payments, mailer, inventory, audit): ...

    def place_order(self, customer_id: int, items: list[str]) -> Order: ...
    def refund(self, order_id: int, amount: int) -> Order: ...
    def export_orders(self, customer_id: int, fmt: str = "csv") -> ExportResult: ...

    def dispatch(self, action: str, payload: dict[str, Any]) -> Any:
        if action == "place_order":
            return self.place_order(payload["customer_id"], payload["items"])
        ...
```

This design exposes four concrete differences:

1. A misspelled string such as `dispatch("exprot_orders", …)` is accepted by the type
   signature and fails when the call runs. This applies to the optional string dispatcher,
   not to the typed direct methods.
2. The dispatcher returns `Any` because its branches return different types. Calling a
   typed method directly preserves that method's return type.
3. Auditing is repeated in each method, and `refund` omits the call.
4. Constructing `OrderService` requires all five collaborators even when a test exercises
   only `refund`.

See [`src/orders/before/service.py`](src/orders/before/service.py) and
[`tests/test_before.py`](tests/test_before.py).

## Split operations into requests and handlers

PyMediate replaces the one class with one **request** and one **handler** per operation. The
request declares what it responds with; the handler takes only what its operation uses:

```python
@dataclass
class RefundOrder(Request[Order]):        # "sending RefundOrder gives back an Order"
    order_id: int
    amount: int

class RefundOrderHandler(RequestHandler[RefundOrder]):
    def __init__(self, store, payments):  # two collaborators, not five
        self._store = store
        self._payments = payments

    def __call__(self, request: RefundOrder) -> Order:
        ...

order = mediator.send(RefundOrder(order_id=1, amount=10))   # order is an Order — typed
```

Everything imports from `pymediate.sync` and `send` returns directly. Auditing moves to one
`AuditBehavior` in [`wiring.py`](src/orders/after/wiring.py). It records every request that
completes successfully, so individual handlers do not repeat that call. See
[`src/orders/after/operations.py`](src/orders/after/operations.py).

## Compare the results

The runtime tests cover missing handlers, audit entries, and focused handler construction.
The type-related rows describe what a static type checker sees.

| `OrderService` (`before/`) | PyMediate (`after/`) |
| --- | --- |
| A mistyped `dispatch("exprot_orders")` fails only at runtime | You send a typed `ExportOrders(...)`; a wrong name is a `NameError` your editor catches, and an unhandled request is refused with `HandlerNotFoundError` naming the type |
| `dispatch(...) -> Any` — `result.orderid` isn't a type error | `send(PlaceOrder(...))` returns `Order`; `order.orderid` is a static error, caught before it runs |
| Auditing is repeated per method; `refund` was missed | One `AuditBehavior` records every successful request; `refund` is audited automatically |
| Testing `refund` demands all five collaborators | `RefundOrderHandler(store, payments)` — construct only the two it uses |

Sending a request with no registered handler raises a specific error:

```text
No handler registered for request type 'ArchiveOrder'
```

The string dispatcher instead raises `ValueError: unknown action: 'exprot_orders'`.

## Read the code

In suggested reading order:

| File | What to read |
| --- | --- |
| [`src/orders/domain.py`](src/orders/domain.py) | **Start here.** The data and five collaborators both implementations share. |
| [`src/orders/before/service.py`](src/orders/before/service.py) | Every operation as an `OrderService` method, plus the optional string dispatcher. |
| [`tests/test_before.py`](tests/test_before.py) | Demonstrates the service implementation's runtime properties. |
| [`src/orders/after/operations.py`](src/orders/after/operations.py) | One request + one handler per operation. |
| [`src/orders/after/wiring.py`](src/orders/after/wiring.py) | `build_mediator` and the single `AuditBehavior`. |
| [`tests/test_after.py`](tests/test_after.py) | Demonstrates missing-handler errors, successful-request auditing, and direct handler tests. |

## Details

- This example compares dispatch typing, audit placement, and constructor dependencies. It
  does not cover dependency injection containers or events.
- This is the synchronous mirror of [005-mediator-vs-service](../005-mediator-vs-service/).
  `RequestHandler`, `Mediator`, and `PipelineBehavior` have synchronous implementations;
  `Request` and `Services` are shared by both APIs.
- Everything is in memory, so each test starts from an empty store.

## Where next

- [010-basic-sync](../010-basic-sync/) — the first synchronous implementation lesson: one
  request, one handler, and one `send()` call.
- [005-mediator-vs-service](../005-mediator-vs-service/) — this orientation on the asynchronous API.
- The essay this example makes runnable:
  [*Using a mediator to reduce change coupling*](https://pymediate.sina-al.uk/articles/using-a-mediator-to-reduce-change-coupling).
- The docs: [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) ·
  [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start).
