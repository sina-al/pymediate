# 080-cqrs

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F080-cqrs%2Fdevcontainer.json)

How do you separate reads from writes? In PyMediate, **CQRS is a naming convention over
request types, not extra machinery** — commands and queries both subclass `Request` and
dispatch through the same `mediator.send()`. What makes it worth doing is giving each side
**its own handler over its own store**, so the write side and the read side can evolve —
and scale — independently.

## Run it

```bash
cd examples/080-cqrs
uv sync
uv run catalog
```

```text
CreateProduct -> ProductId(product_id=1)
AdjustStock   -> StockAdjustedResult(product_id=1, new_stock=7)
GetProduct    -> ProductView(product_id=1, name='Keyboard', price=49.99, stock=7, in_stock=True, price_tier='standard')
SearchProducts -> 1 product(s) in stock
```

Look at the shapes: `CreateProduct` and `AdjustStock` return just enough to confirm the
write; `GetProduct` returns a `ProductView` with two fields — `in_stock`, `price_tier` — that
don't exist anywhere on the write side. That's the split, made visible in one demo run.

## Two stores, two shapes

```python
class WriteStore:
    """The write side: a normalized primary store, indexed by id."""
    def create(self, name: str, price: float, stock: int) -> Product: ...
    def adjust_stock(self, product_id: int, delta: int) -> Product: ...

class ReadStore:
    """The read side: a denormalized projection, written only by the event projectors."""
    def find(self, product_id: int) -> ProductView | None: ...
    def search(self, *, in_stock_only: bool = False) -> list[ProductView]: ...
```

`Product` (write) has exactly the fields a write needs to validate and mutate. `ProductView`
(read) has those *plus* `in_stock` and `price_tier` — derived fields a reader wants that the
write side has no reason to store. Two stores, two shapes, each optimized for what it's for.

## Commands write; queries read; an event connects them

```python
class CreateProductHandler(RequestHandler[CreateProduct]):
    async def __call__(self, request: CreateProduct) -> ProductId:
        product = self._store.create(request.name, request.price, request.stock)
        await self._publisher.publish(ProductCreated(product_id=product.product_id, ...))
        return ProductId(product_id=product.product_id)   # minimal — just the new id

class GetProductHandler(RequestHandler[GetProduct]):
    async def __call__(self, request: GetProduct) -> ProductView:
        return self._store.find(request.product_id)        # rich — the full read model
```

A command handler never touches `ReadStore`, and a query handler never touches `WriteStore`
— each side stays ignorant of the other's storage. The read side learns what happened only
by subscribing to the events commands publish (`ProductCreatedProjector`,
`StockAdjustedProjector`), the same `publish()` fan-out from
[020-events](../020-events/). In a real system that projector would run against a separate
replica or search index; here it's in-process to stay a runnable, self-contained example.

## Wiring: one `Services` collection, one `Mediator`

```python
services = Services()
services.add(CreateProductHandler(write_store, publisher))
services.add(AdjustStockHandler(write_store, publisher))
services.add(GetProductHandler(read_store))
services.add(SearchProductsHandler(read_store))
services.add(ProductCreatedProjector(read_store))
services.add(StockAdjustedProjector(read_store))
mediator = Mediator(services.provider())
```

Commands, queries, and the projectors that connect them all register on the same collection
and dispatch through the same mediator. There's no second mediator, no parallel dispatch
path — CQRS lives entirely in which store each handler is allowed to touch.

## The files

| File | What it is |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** `WriteStore`/`ReadStore`, the events between them, and the command/query request types. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | The command handlers, the query handlers, and the projectors that keep the read side in sync. |
| [`src/catalog/app.py`](src/catalog/app.py) | `build_mediator` and the demo. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Proves the split: minimal command responses, the denormalized view, separate store shapes, event-driven updates: `uv run pytest` → `7 passed`. |

## Small print

- `LateBoundPublisher` exists to solve a wiring order problem: a command handler needs to
  publish through the `Mediator`, but the `Mediator` doesn't exist until *after* the
  handlers are registered. It's bound to the real mediator once construction finishes — the
  same pattern [050-handler-composition](../050-handler-composition/) uses for a handler
  that dispatches sub-requests.
- A production read side is usually a separate replica, cache, or search index kept in sync
  asynchronously — not an in-process dict updated synchronously in the same call. This
  example keeps it synchronous and in-process purely to stay runnable as a self-contained
  example; the shape of the split is the same either way.

## Where next

- [080-cqrs-sync](../080-cqrs-sync/) — the same command/query split on `pymediate.sync`.
- [020-events](../020-events/) — the `publish()` fan-out this example's projectors build on.
- [040-pipeline-behaviors](../040-pipeline-behaviors/) — a `PipelineBehavior[Query]` that
  caches reads, if you want to add caching on top of this split.
- The docs: [CQRS example](https://pymediate.sina-al.uk/docs/examples/cqrs).
