# Error handling

PyMediate deliberately stays out of your error handling. Handlers raise ordinary
Python exceptions, `send` lets them propagate unchanged, and it's up to the edge of
your application to decide what a given failure means to a caller. That hands-off
stance is the point: it's what lets the same core run behind a web framework, a CLI,
or a background worker without change.

Two families of error show up in a PyMediate application, and keeping them apart is
what keeps the core portable:

- **Domain errors** — raised by your handlers to signal business-rule violations
  (`InsufficientFundsError`, `ProductNotFoundError`). Plain exceptions, no framework
  knowledge.
- **Framework errors** — HTTP status codes, JSON error bodies, `HTTPException`. These
  belong to the web layer, not to a handler.

## Domain errors

A handler's job is to describe *what went wrong in the domain*, not how some transport
should report it. Model those failures as a small exception hierarchy so callers can
catch at whatever granularity they need.

```python
class ShopError(Exception):
    """Base for every error the shop domain can raise."""

class ProductNotFoundError(ShopError):
    def __init__(self, product_id: int):
        self.product_id = product_id
        super().__init__(f"Product not found: {product_id}")

class OutOfStockError(ShopError):
    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Product {product_id} out of stock: "
            f"requested {requested}, available {available}"
        )
```

A handler raises them and nothing else — no status codes, no `abort()`, no imports from
your web framework.

```python
class PlaceOrderHandler(Handler[PlaceOrderRequest]):
    def __call__(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        product = self.database.get_product(request.product_id)
        if not product:
            raise ProductNotFoundError(request.product_id)
        if product.stock < request.quantity:
            raise OutOfStockError(request.product_id, request.quantity, product.stock)

        order_id = self.database.create_order(request)
        return PlaceOrderResponse(order_id=order_id)
```

## Framework errors

A handler must speak only in domain terms. The blatant way to break that is to raise the
web framework's own exception straight from a handler, which drags the framework's types
into your core.

```python
# Leak: the handler now depends on a web framework.
raise HTTPException(status_code=404, detail="Product not found")
```

Reaching for your own exception class instead doesn't fix anything if you smuggle the same
transport detail inside it. This looks framework-independent, and isn't.

```python
# Also a leak: a domain error that carries its own HTTP status.
class ProductNotFoundError(ShopError):
    http_status = 404

    def __init__(self, product_id: int):
        self.product_id = product_id
        super().__init__(f"Product not found: {product_id}")
```

The exception is yours, but `http_status` is a fact about HTTP, and HTTP is one transport
out of many. The domain's job is to say *what* happened — this product doesn't exist.
Deciding that a missing product maps to `404` is the web edge's job, and it only means
anything when an HTTP request is actually in play. Either form — the framework exception or
the `http_status` attribute — pins your core to one transport.

### Why this matters

The coupling costs nothing on the day you write it. It sends the bill the day you try to
reuse the core — which is the whole reason the core exists. Suppose the shop needs a second
entry point: a nightly batch script that replays failed orders from a partner's CSV feed.
`PlaceOrderHandler` is just a class, so this should be the mediator pattern's easiest win —
point a new script at the same `mediator.send()` call and go home. You write it and run it.

```
$ python replay_orders.py
Traceback (most recent call last):
  File "replay_orders.py", line 40, in <module>
    response = mediator.send(PlaceOrderRequest(...))
  ...
  File "shop/handlers.py", line 12, in __call__
    raise HTTPException(status_code=404, detail="Product not found")
fastapi.exceptions.HTTPException: 404: Product not found
```

A batch script just failed with an HTTP error. There's no server in this program, no client,
no request — nothing a 404 could be sent *to* — yet there it is at the bottom of the
traceback. Look at what it took to get even this far: `replay_orders.py` can't run without
FastAPI installed, because the domain can't say "product not found" without it. To catch the
error and skip the row, the batch script must `import fastapi` too. A CSV-processing job now
carries a web framework as a load-bearing dependency, and every future entry point — the
queue consumer, the admin CLI, the test suite — inherits the same passenger.

Swapping frameworks is where it fully unravels: migrating FastAPI to Flask should mean
rewriting routes, but your *handlers* raise `fastapi.exceptions.HTTPException`, so the
migration now reaches into the domain layer — the one part of the codebase the architecture
promised would never care.

That's the real cost: the leak doesn't hurt where you wrote it, it hurts everywhere you
planned to go next. Keep transport out of the domain and every new edge is just a new
translation; let it in and every new edge inherits a framework it has no use for. Which
raises the practical question — where should that translation live?

## Mapping domain errors at the edge

Every mainstream web framework has a construct for turning an exception into a response.
Register your domain-error mapping there — once, centrally — and keep the mediator call
in your routes down to the happy path.

**Flask** — `register_error_handler` (or the `@app.errorhandler` decorator).

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.errorhandler(ProductNotFoundError)
def handle_not_found(err: ProductNotFoundError):
    return jsonify(error=str(err), product_id=err.product_id), 404

@app.errorhandler(OutOfStockError)
def handle_out_of_stock(err: OutOfStockError):
    return jsonify(error=str(err), available=err.available), 409

@app.post("/orders")
def place_order():
    # No try/except: the route describes success; the handlers above map failure.
    response = mediator.send(PlaceOrderRequest(...))
    return jsonify(order_id=response.order_id), 201
```

**FastAPI** — `add_exception_handler` (or the `@app.exception_handler` decorator).

```python
from fastapi import FastAPI, Request as HTTPRequest
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(ProductNotFoundError)
async def handle_not_found(request: HTTPRequest, err: ProductNotFoundError):
    return JSONResponse(status_code=404, content={"error": str(err)})

@app.exception_handler(OutOfStockError)
async def handle_out_of_stock(request: HTTPRequest, err: OutOfStockError):
    return JSONResponse(status_code=409, content={"error": str(err)})

@app.post("/orders")
def place_order():
    response = mediator.send(PlaceOrderRequest(...))
    return {"order_id": response.order_id}
```

Registering against the `ShopError` base maps the whole hierarchy in one handler; adding
a per-subclass handler only where a failure needs a distinct status code. The core stays
clean, and swapping Flask for FastAPI (or adding a CLI) means rewriting only this mapping
layer.

## A tempting trap: mapping inside a behavior

Because a [pipeline behavior](pipeline-behaviors.md) wraps every dispatch, it looks like
the perfect place to catch domain errors and turn them into responses.

```python
# Tempting, but it pulls the web framework into your core pipeline.
class HttpErrorMappingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        try:
            return next()
        except ProductNotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err))  # framework leak
        except OutOfStockError as err:
            raise HTTPException(status_code=409, detail=str(err))
```

It centralizes the mapping and runs for free on every request — but it drags
`HTTPException` back *inside* the mediator, exactly the coupling the domain errors were
designed to avoid. The mediator no longer runs cleanly in a CLI or a worker.

The damage is at least contained: it's a single, clearly specialized behavior, so a
different deployment can simply leave it out of its behavior list and register a
plain-exception mapping instead. But prefer the framework's own error-handling
construct — mapping at the edge keeps the leak out of the pipeline entirely, which is
strictly the more portable choice.

## PyMediate's own errors

PyMediate raises its own exceptions, all subclasses of `PyMediateError` (which carries an
optional `docs_path` to the relevant guide). They split into two groups by *when* they
fire, and the two call for opposite treatment.

### Definition-time errors — fatal, not meant to be caught

PyMediate validates a `Handler` or `Request` subclass at the point it is *defined*, so
these are raised while your modules are being imported — before the app is even running:

- `InvalidHandlerSignatureError` — a `Handler.__call__` with the wrong shape.
- `InvalidRequestTypeError` — a handler parameterized on something that isn't a `Request`.
- `ResponseTypeMismatchError` — a handler's return annotation disagrees with its request's
  response type.
- `HandlerAlreadyRegisteredError` — two handlers registered for the same request type.

There is nothing to catch, because the `import` that defines the offending class is what
raises. A program with one of these can't start — it's a programming mistake, like a
`SyntaxError`. Read the message, fix the code; don't wrap class definitions in `try`.

### Dispatch-time errors — catchable

These fire while a request is being routed, and you can handle them like any runtime
exception:

- `HandlerNotFoundError` — `mediator.send()` received a request with no registered handler.
- `ServiceNotFoundError` — a `ServiceProvider.get()` couldn't resolve a requested type.

Both usually signal a *misconfigured deployment* (a handler or service was never
registered) rather than bad client input, so at a web edge they map to a 500, not a 4xx.

```python
from pymediate import HandlerNotFoundError

try:
    response = mediator.send(GetUserRequest(user_id=1))
except HandlerNotFoundError as err:
    # A handler is missing from the container — a config bug, not the caller's fault.
    logger.error("No handler registered for %s", err.request_type.__name__)
    raise
```

---

## Next steps

- [Pipeline behaviors](pipeline-behaviors.md) — cross-cutting logic, and why error mapping
  usually shouldn't live here.
- [FastAPI example](../examples/fastapi.md) — a full edge that maps exceptions to responses.
- [Handlers](handlers.md) — where domain errors are raised.
