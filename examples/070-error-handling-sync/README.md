# 070-error-handling-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F070-error-handling-sync%2Fdevcontainer.json)

Synchronous handlers raise errors that describe domain failures, such as a missing product.
Each external interface converts those errors into its own result: HTTP status codes for
FastAPI and process exit codes for the command-line interface.

## Run

From this directory:

```bash
uv sync
uv run pytest
```

```text
8 passed
```

The command-line interface shows the error text and returns a nonzero exit status:

```console
$ uv run shop-cli get 999
error: product not found: 999
$ echo $?
3

$ uv run shop-cli order 2 3
error: product 2 out of stock: requested 3, available 0
$ echo $?
4

$ uv run shop-cli get 1
Product(product_id=1, name='Widget', stock=5)
$ echo $?
0
```

## Raise domain errors in handlers

```python
class ProductNotFoundError(ShopError):
    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")

class GetProductHandler(RequestHandler[GetProduct]):
    def __call__(self, request: GetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            raise ProductNotFoundError(request.product_id)
        return product
```

The core contains no HTTP status or process exit code. It records what failed, leaving each
interface to decide how to report that failure.

## Convert errors at each boundary

FastAPI registers one HTTP conversion:

```python
@app.exception_handler(ProductNotFoundError)
def on_not_found(request, error):
    return JSONResponse(status_code=404, content={"error": str(error)})
```

The command-line interface registers a different conversion:

```python
def send_as_cli(mediator, request) -> int:
    try:
        result = mediator.send(request)
    except ProductNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    print(result)
    return 0
```

Routes and commands do not repeat these mappings. FastAPI maps `OutOfStockError` to 409, while
the command-line interface maps it to exit code 4.

## Keep HTTP exceptions at the HTTP boundary

`src/shop/leaky.py` contains a comparison handler that raises FastAPI's `HTTPException`.
When called through the command-line mapping, that exception propagates because the mapping
handles domain errors only.

```python
def test_http_exception_has_no_cli_mapping():
    with pytest.raises(HTTPException):
        send_as_cli(build_leaky_mediator(), LeakyGetProduct(product_id=999))
```

The issue is not the exception class itself; it is deciding an HTTP response inside code also
used by non-HTTP callers.

## Read the code

| File | What to read |
| --- | --- |
| [`src/shop/core.py`](src/shop/core.py) | Start here for domain errors, requests, and handlers. |
| [`src/shop/api.py`](src/shop/api.py) | Domain errors converted to HTTP 404 and 409. |
| [`src/shop/cli.py`](src/shop/cli.py) | The same errors converted to exit codes. |
| [`src/shop/leaky.py`](src/shop/leaky.py) | The HTTP-coupled comparison handler. |
| [`tests/test_error_handling.py`](tests/test_error_handling.py) | Both mappings and the comparison case. |

## Details

Map application errors at the outer boundary that knows the response format. A pipeline
behavior can centralize domain logging or retries, but converting an error to `HTTPException`
inside that behavior still couples mediator dispatch to HTTP.

PyMediate's configuration errors are separate from the shop's domain errors. Errors such as
`HandlerNotFoundError` normally indicate incomplete registration and should be reported as
server failures rather than client input errors.

## Where next

- [075-authorization-sync](../075-authorization-sync/) distinguishes missing authentication
  from an authenticated authorization denial.
- [070-error-handling](../070-error-handling/) shows the asynchronous API.
- Read the [error handling guide](https://pymediate.sina-al.uk/docs/guide/error-handling).
