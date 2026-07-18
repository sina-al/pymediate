# why a mediator? (sync)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F005-why-a-mediator-sync%2Fdevcontainer.json)

> *"Why can't I just put everything in one service class? I'll pass in what it needs and
> call a method. Why add a library?"*

Fair question — and this example answers it by letting you **run both**. Same orders
feature, built twice over the same domain: once as one `OrderService` god class
([`before/`](src/orders/before/)), once as pymediate handlers ([`after/`](src/orders/after/)).
The before/ version works, then hurts in four specific ways as it grows. The after/ version
does the identical job with each hurt gone. Nothing here is narrated at you — every claim is
a test that runs.

This is the **synchronous** twin of [005-why-a-mediator](../005-why-a-mediator/): the same
lesson on `pymediate.sync`, no event loop. Diff the two directories to see how small the
sync delta is — the handlers lose `async`/`await` and nothing else.

## Run it

```bash
cd examples/005-why-a-mediator-sync
uv sync
uv run pytest
```

```text
tests/test_after.py ....                                                 [ 50%]
tests/test_before.py ....                                                [100%]

8 passed
```

`test_before.py` passes by asserting the god service's four pains are **real**.
`test_after.py` passes by asserting each one is **gone**. Read them side by side — that
diff is the whole lesson.

## The one big service, and where it hurts

Here's the shape most teams reach for first, and it's a good one — direct, readable,
approved in a five-minute review. Every operation is a method; every collaborator it could
need is handed in once:

```python
class OrderService:
    def __init__(self, store, payments, mailer, inventory, audit): ...

    def place_order(self, customer_id, items): ...
    def refund(self, order_id, amount): ...
    def export_orders(self, customer_id, fmt="csv"): ...

    def dispatch(self, action: str, payload: dict) -> Any:   # the string front door
        if action == "place_order":
            return self.place_order(payload["customer_id"], payload["items"])
        ...
```

Give it two years of reasonable commits and four costs surface — see
[`src/orders/before/service.py`](src/orders/before/service.py) and the tests that pin each
one down:

1. **A mistyped action is a runtime problem, not a typing one.** `dispatch("exprot_orders", …)`
   is a perfectly valid `str`; nothing catches it until it runs.
2. **The response is `Any`.** `dispatch` returns different types per branch, so its only
   honest return type switches the type checker off — `result.orderid` (a typo) sails
   straight past it.
3. **A cross-cutting concern is copy-pasted per method.** Auditing is a `self._audit.record(…)`
   line at the top of each method — and `refund`, added later, never got it. The trail
   silently misses every refund, and nothing flagged the omission.
4. **Testing one operation costs the whole world.** `refund` touches two collaborators, but
   there's no way to build an `OrderService` — and so no way to test `refund` — without
   supplying all five.

## The same feature, un-braided

pymediate replaces the one class with one **request** and one **handler** per operation. The
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

Everything imports from `pymediate.sync` and `send` returns directly — no `await`. Auditing
moves to one `AuditBehavior` that wraps every request in
[`wiring.py`](src/orders/after/wiring.py), so no operation repeats it — and none can forget
it. See [`src/orders/after/operations.py`](src/orders/after/operations.py).

## Four pains, four fixes

Each row is a pair of passing tests — the before/ one asserts the pain, the after/ one
asserts it resolved.

| The god service (`before/`) | pymediate (`after/`) |
| --- | --- |
| A mistyped `dispatch("exprot_orders")` fails only at runtime | You send a typed `ExportOrders(...)`; a wrong name is a `NameError` your editor catches, and an unhandled request is refused with `HandlerNotFoundError` naming the type |
| `dispatch(...) -> Any` — `result.orderid` isn't a type error | `send(PlaceOrder(...))` returns `Order`; `order.orderid` is a static error, caught before it runs |
| Auditing copy-pasted per method; `refund` was missed | One `AuditBehavior` wraps every request; `refund` is audited automatically |
| Testing `refund` demands all five collaborators | `RefundOrderHandler(store, payments)` — construct only the two it uses |

That last fix has a name worth knowing: sending a request whose handler nobody wrote is
refused up front, clearly —

```text
No handler registered for request type 'ArchiveOrder'

💡 Possible solutions:
  1. Register a handler: services.add(your_handler_instance)
  ...
```

— rather than the god service's opaque `ValueError: unknown action: 'exprot_orders'`.

## The files

In suggested reading order:

| File | What it is |
| --- | --- |
| [`src/orders/domain.py`](src/orders/domain.py) | **Start here.** The data and the five collaborators both packages share. |
| [`src/orders/before/service.py`](src/orders/before/service.py) | The god service — every operation a method, with the four pains marked in comments. |
| [`tests/test_before.py`](tests/test_before.py) | Runs the god service and asserts each pain is real. |
| [`src/orders/after/operations.py`](src/orders/after/operations.py) | One request + one handler per operation. |
| [`src/orders/after/wiring.py`](src/orders/after/wiring.py) | `build_mediator` and the single `AuditBehavior`. |
| [`tests/test_after.py`](tests/test_after.py) | The mirror of `test_before.py` — each pain, resolved. |

## Small print

- **This is a *why*, not a tour.** It shows exactly what decomposing into handlers buys and
  nothing else — no DI container, no events, one behavior only because the audit pain needs
  one. Later examples teach those.
- The god service is deliberately *not* a strawman. It's a competent design; the point is
  that it degrades from reasonable commits, not from a mistake.
- This is the sync mirror of the async [005-why-a-mediator](../005-why-a-mediator/), built on
  `pymediate.sync`. Only `RequestHandler`, `Mediator`, and `PipelineBehavior` differ between
  the two sides; `Request` and `Services` are the same objects.
- Everything is in memory, so each test starts from an empty store.

## Where next

- [005-why-a-mediator](../005-why-a-mediator/) — the async original this mirrors.
- [010-basic-sync](../010-basic-sync/) — now that you know *why*, the smallest *how* on the sync API:
  the core `send()` loop, in one file.
- The essay this example makes runnable:
  [*Nobody wants to touch that code*](https://pymediate.sina-al.uk/articles/nobody-wants-to-touch-that-code).
- The docs: [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) ·
  [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start).
