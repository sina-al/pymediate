# 070-error-handling-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F070-error-handling-sync%2Fdevcontainer.json)

The synchronous mirror of [070-error-handling](../070-error-handling/), on `pymediate.sync`.
Same story: handlers raise **plain domain errors**, and each **edge** maps them to its own
transport — a `404` on the FastAPI app, an **exit code** on the CLI. And the same
anti-pattern (`raise HTTPException` from a handler) breaks the non-HTTP caller.

## Run it

```bash
cd examples/070-error-handling-sync
uv sync
uv run pytest
```

```text
8 passed
```

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
class GetProductHandler(RequestHandler[GetProduct]):
    def __call__(self, request: GetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            raise ProductNotFoundError(request.product_id)   # what happened, not how to report it
        return product
```

`core.py` imports pymediate and the standard library — no FastAPI, no `http_status`, no exit
codes. (Only the API import and the `async`/`await` mechanics differ from the async twin.)

## Each edge maps the same error its own way

```python
# api.py — the web edge
@app.exception_handler(ProductNotFoundError)
def on_not_found(request, err):
    return JSONResponse(status_code=404, content={"error": str(err)})

# cli.py — the CLI edge
def send_as_cli(mediator, request) -> int:
    try:
        result = mediator.send(request)
    except ProductNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return 3                                  # the same error, a different meaning
    ...
```

## The anti-pattern: `raise HTTPException` from a handler

[`src/shop/leaky.py`](src/shop/leaky.py) imports FastAPI into a core handler — the tell — and
raises `HTTPException`. Driven through the CLI it escapes the domain-error mapping:

```python
def test_leaked_http_exception_escapes_the_cli():
    with pytest.raises(HTTPException):           # sails past `except ProductNotFoundError`
        send_as_cli(build_leaky_mediator(), LeakyGetProduct(product_id=999))
```

A batch job crashing with an HTTP error and no client to send a 404 to — exactly what
keeping transport out of the core prevents.

## The files

| File | What it is |
| --- | --- |
| [`src/shop/core.py`](src/shop/core.py) | **Start here.** Domain errors, requests, handlers — no transport anywhere. |
| [`src/shop/api.py`](src/shop/api.py) | The web edge: domain errors → `404` / `409`. |
| [`src/shop/cli.py`](src/shop/cli.py) | The CLI edge: the same errors → exit codes. |
| [`src/shop/leaky.py`](src/shop/leaky.py) | The anti-pattern, isolated. Imports FastAPI — the tell. |
| [`tests/test_error_handling.py`](tests/test_error_handling.py) | Both transports' mappings, and the leak breaking the CLI: `uv run pytest` → `8 passed`. |

## Where next

- [070-error-handling](../070-error-handling/) — the async original.
- [075-authorization](../075-authorization/) — authn at the edge, authz in the core.
- The docs: [error handling guide](https://pymediate.sina-al.uk/docs/guide/error-handling).
