<p align="center">
  <img src="https://github.com/sina-al/pymediate/blob/main/assets/logo.svg?raw=true" alt="PyMediate logo" width="400"><br><br>
  <b>Typed in-process request dispatch for Python 3.12+</b><br><br>

  <a href="https://pypi.org/project/pymediate/">
    <img src="https://img.shields.io/pypi/v/pymediate" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/pymediate/">
    <img src="https://img.shields.io/pypi/pyversions/pymediate" alt="Python versions">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
  </a>
  <a href="https://pymediate.sina-al.uk">
    <img src="https://img.shields.io/badge/docs-pymediate.sina--al.uk-blue" alt="Documentation">
  </a>
  <br>
  <a href="https://github.com/sina-al/pymediate/actions/workflows/test.yml">
    <img src="https://github.com/sina-al/pymediate/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/sina-al/pymediate/tree/python-coverage-comment-action-data">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/sina-al/pymediate/python-coverage-comment-action-data/endpoint.json" alt="Coverage">
  </a>
  <a href="https://mypy-lang.org/">
    <img src="https://img.shields.io/badge/mypy-strict-blue" alt="Checked with mypy (strict)">
  </a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/sina-al/pymediate">
    <img src="https://api.scorecard.dev/projects/github.com/sina-al/pymediate/badge" alt="OpenSSF Scorecard">
  </a>
  <a href="https://github.com/sina-al/pymediate/attestations">
    <img src="https://slsa.dev/images/gh-badge-level2.svg" alt="SLSA Build Level 2">
  </a>
</p>

---

PyMediate routes typed requests to handlers. A request declares its response type, so
`Mediator.send()` preserves that type for static type checkers and editors.

## Installation

```bash
pip install pymediate
```

The core package has no required dependencies. Install the optional Dependency Injector
integration with `pip install 'pymediate[di]'`.

## First request

```python
import asyncio
from dataclasses import dataclass

from pymediate import Mediator, Request, RequestHandler, Services


@dataclass(frozen=True)
class OrderReceipt:
    order_id: int
    summary: str


@dataclass(frozen=True)
class PlaceOrder(Request[OrderReceipt]):
    customer_id: int
    item: str
    quantity: int


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    async def __call__(self, request: PlaceOrder) -> OrderReceipt:
        return OrderReceipt(
            order_id=42,
            summary=f"{request.quantity} × {request.item}",
        )


async def main() -> None:
    mediator = Mediator(Services().add(PlaceOrderHandler()).provider())
    receipt = await mediator.send(
        PlaceOrder(customer_id=7, item="tea", quantity=2),
    )
    print(receipt.order_id, receipt.summary)


asyncio.run(main())
```

The program prints:

```text
42 2 × tea
```

Read the declarations as follows:

- `OrderReceipt` is the response.
- `PlaceOrder(Request[OrderReceipt])` is a request for an `OrderReceipt`.
- `PlaceOrderHandler(RequestHandler[PlaceOrder])` handles `PlaceOrder` requests.

The [introduction](https://pymediate.sina-al.uk/docs) contains an interactive guide to these
relationships. The [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start)
explains the complete dispatch flow.

## API at a glance

| Need | API | Result |
| --- | --- | --- |
| Send a request to one handler | `Mediator.send()` | One response, inferred from `Request[T]` |
| Yield results over time | `Mediator.stream()` | Typed chunks from `StreamRequest[T]` |
| Notify zero or more subscribers | `Mediator.publish()` | No response |
| Wrap request handling | `PipelineBehavior` | Shared processing around `send()` |
| Supply handlers and behaviors | `Services` or another `ServiceProvider` | Resolved instances |

The top-level package is asynchronous. `pymediate.sync` provides corresponding blocking mediator
and handler classes. Shared message types, services, and errors are the same objects in both
namespaces.

## Type checking and validation

`Request[T]` records the return type used by `send()` at static call sites. Separately, PyMediate
checks a request handler's parameter annotation, return annotation, and asynchronous or synchronous
form when Python defines the handler class.

Configuration can still fail during dispatch. For example, sending a request without a registered
handler instance raises an error at that point. The [type-safety guide](https://pymediate.sina-al.uk/docs/guide/type-safety)
describes which checks happen statically, at class definition, and during dispatch.

## Scope and trade-offs

PyMediate provides in-process dispatch. It does not provide a task queue, choose persistence, or
require CQRS or hexagonal architecture. Direct calls are often clearer when callers can depend on
their collaborators without repeated wiring, and a small hand-written dispatcher can be enough.

The article [*Using a mediator to reduce change coupling*](https://pymediate.sina-al.uk/articles/using-a-mediator-to-reduce-change-coupling)
develops the case for a mediator and covers the added indirection, registration, and runtime cost.
The [comparison](https://pymediate.sina-al.uk/docs/comparison) documents the current feature set,
dated dispatch benchmarks, and a runnable benchmark script.

## Documentation

- [Introduction](https://pymediate.sina-al.uk/docs)
- [Quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start)
- [Core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts)
- [Guides](https://pymediate.sina-al.uk/docs/guide/requests-responses)
- [API reference](https://pymediate.sina-al.uk/docs/api)
- [Runnable examples](https://github.com/sina-al/pymediate/tree/main/examples)

## Development

```bash
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras --group test

uv run poe test
uv run poe check:all
```

Run `uv run poe` to list the repository tasks. See
[CONTRIBUTING.md](https://github.com/sina-al/pymediate/blob/main/CONTRIBUTING.md) for the
contribution process.

## Versioning

PyMediate follows [ZeroVer](https://0ver.org/): the major version remains `0`. A minor release
(`0.X.0`) can contain a breaking API change or a backward-compatible feature. A patch release
(`0.X.Y`) contains changes that do not alter the public API.

## License

PyMediate is available under the
[MIT License](https://github.com/sina-al/pymediate/blob/main/LICENSE).
