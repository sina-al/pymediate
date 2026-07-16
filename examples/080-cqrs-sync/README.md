# 080-cqrs-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F080-cqrs-sync%2Fdevcontainer.json)

The synchronous mirror of [080-cqrs](../080-cqrs/), on `pymediate.sync`. Same split: commands
write through `WriteStore` and announce what changed; queries read a denormalized `ReadStore`
kept in sync by subscribing to those announcements — one `Mediator`, two stores, two shapes.

## Run it

```bash
cd examples/080-cqrs-sync
uv sync
uv run catalog
```

```text
CreateProduct -> ProductId(product_id=1)
AdjustStock   -> StockAdjustedResult(product_id=1, new_stock=7)
GetProduct    -> ProductView(product_id=1, name='Keyboard', price=49.99, stock=7, in_stock=True, price_tier='standard')
SearchProducts -> 1 product(s) in stock
```

## What changes from the async version

Only the API import and the mechanics — the split itself is identical:

```python
# domain.py
from pymediate.sync import Event, Mediator, Request

# handlers.py
class CreateProductHandler(RequestHandler[CreateProduct]):
    def __call__(self, request: CreateProduct) -> ProductId:   # no async
        product = self._store.create(request.name, request.price, request.stock)
        self._publisher.publish(ProductCreated(product_id=product.product_id, ...))  # no await
        return ProductId(product_id=product.product_id)
```

Every store, event, command, query, and projector in [`domain.py`](src/catalog/domain.py)
and [`handlers.py`](src/catalog/handlers.py) is byte-for-byte the same shape as the async
twin, minus `async`/`await`.

## The files

| File | What it is |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** `WriteStore`/`ReadStore`, the events between them, and the command/query request types. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | The command handlers, the query handlers, and the projectors that keep the read side in sync. |
| [`src/catalog/app.py`](src/catalog/app.py) | `build_mediator` and the demo. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Proves the split: minimal command responses, the denormalized view, separate store shapes, event-driven updates: `uv run pytest` → `7 passed`. |

## Where next

- [080-cqrs](../080-cqrs/) — the async default, with the full explanation of the split.
- [020-events-sync](../020-events-sync/) — the `publish()` fan-out this example's projectors
  build on, on `pymediate.sync`.
- The docs: [CQRS example](https://pymediate.sina-al.uk/docs/examples/cqrs).
