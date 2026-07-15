# 070-error-handling

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F070-error-handling%2Fdevcontainer.json)

Where do you handle errors — and why not just `raise HTTPException` from a handler? Because
the moment a handler knows about HTTP, the core stops being portable. In PyMediate a handler
raises a **plain domain error**; each **edge** decides what that error means to its caller.
This example runs one core behind **two transports** — a FastAPI app and a CLI — where the
same `ProductNotFoundError` becomes a `404` on the web and an **exit code 3** on the command
line. Then it shows the anti-pattern breaking a non-HTTP caller.

## Run it

```bash
cd examples/070-error-handling
uv sync
uv run pytest
```

```text
8 passed
```

Those eight tests drive the same core through both transports and prove each maps the domain
errors its own way — plus that the leaky handler breaks the CLI.

Try the CLI yourself — the same core, no web server in sight:

```console
$ uv run shop-cli get 999
error: product not found: 999          # exit code 3

$ uv run shop-cli order 2 3
error: product 2 out of stock: requested 3, available 0   # exit code 4

$ uv run shop-cli get 1
Product(product_id=1, name='Widget', stock=5)             # exit code 0
```

## The core raises domain errors — nothing else

```python
class ShopError(Exception): ...
class ProductNotFoundError(ShopError):
    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")

class GetProductHandler(RequestHandler[GetProduct]):
    async def __call__(self, request: GetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            raise ProductNotFoundError(request.product_id)   # what happened, not how to report it
        return product
```

`core.py` imports pymediate and the standard library — **no FastAPI, no `http_status`, no
exit codes**. The handler says *this product doesn't exist*; deciding that a missing product
means `404` (or exit `3`) is a transport's job, not the domain's.

## Each edge maps the same error its own way

```python
# api.py — the web edge
@app.exception_handler(ProductNotFoundError)
async def on_not_found(request, err):
    return JSONResponse(status_code=404, content={"error": str(err)})

# cli.py — the CLI edge
def send_as_cli(mediator, request) -> int:
    try:
        result = asyncio.run(mediator.send(request))
    except ProductNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return 3                                  # the same error, a different meaning
    ...
```

One mapping per transport, registered once. Routes and CLI commands describe only the happy
path; failure is translated centrally. Swapping FastAPI for Flask — or adding this CLI —
touches only the mapping layer, never a handler.

## The anti-pattern: `raise HTTPException` from a handler

[`src/shop/leaky.py`](src/shop/leaky.py) does it the wrong way, and its import list gives it
away — a *core* handler that imports a web framework:

```python
from fastapi import HTTPException            # ← the smell

class LeakyGetProductHandler(RequestHandler[LeakyGetProduct]):
    async def __call__(self, request):
        product = self._catalog.get(request.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
```

Drive that handler through the CLI and watch it break:

```python
def test_leaked_http_exception_escapes_the_cli():
    with pytest.raises(HTTPException):           # sails past `except ProductNotFoundError`
        send_as_cli(build_leaky_mediator(), LeakyGetProduct(product_id=999))
```

The CLI's mapping catches *domain* errors. An `HTTPException` isn't one, so it escapes — a
batch job crashing with an HTTP error and no client to send a 404 to. That's what "keep
transport out of the core" is protecting you from.

## The files

| File | What it is |
| --- | --- |
| [`src/shop/core.py`](src/shop/core.py) | **Start here.** Domain errors, requests, handlers — no transport anywhere. |
| [`src/shop/api.py`](src/shop/api.py) | The web edge: domain errors → `404` / `409`. |
| [`src/shop/cli.py`](src/shop/cli.py) | The CLI edge: the same errors → exit codes. |
| [`src/shop/leaky.py`](src/shop/leaky.py) | The anti-pattern, isolated. Imports FastAPI — the tell. |
| [`tests/test_error_handling.py`](tests/test_error_handling.py) | Both transports' mappings, and the leak breaking the CLI: `uv run pytest` → `8 passed`. |

## Small print

- **Don't map errors in a behavior.** A `PipelineBehavior` catching `ProductNotFoundError`
  and raising `HTTPException` centralizes the mapping but drags the framework back *inside*
  the mediator — the very coupling domain errors avoid. Map at the edge instead.
- **PyMediate's own errors** split in two. *Definition-time* errors
  (`InvalidHandlerSignatureError`, `HandlerAlreadyRegisteredError`, …) fire while your
  modules import — programming mistakes, not something to catch. *Dispatch-time* errors
  (`HandlerNotFoundError`, `ServiceNotFoundError`) fire during `send()` and usually mean a
  misconfigured deployment, so an edge maps them to `500`, not a 4xx. This example is about
  *your* domain errors, not these.

## Where next

- [070-error-handling-sync](../070-error-handling-sync/) — the same two-transport story on
  `pymediate.sync`.
- [075-authorization](../075-authorization/) — authentication at the edge, authorization in
  the core: the same edge-vs-core split, one layer up.
- The docs: [error handling guide](https://pymediate.sina-al.uk/docs/guide/error-handling).
