"""Pytest plugin backing `poe test:docs` — executes the project's documentation snippets.

Loaded explicitly with `-p tests.markdown_docs_plugin` by the `test:docs` poe task, never
by the ordinary test run, so nothing here affects `poe test`.

It supplies three things pytest-markdown-docs needs to run this project's docs:

1. `pytest_markdown_docs_globals` seeds each snippet with the recurring example cast, so the
   deliberately-terse fragments in `docs/content/` and the docstring `Examples:` sections run
   unmodified. Fragments that build on an *earlier fence of the same page* use
   pytest-markdown-docs' `continuation` marker instead; this cast is only for the names that
   recur across pages.
2. `_isolate_registries` clears the process-global handler registry around every snippet.
   Handlers register at class-definition time, so without this the second page to define a
   handler for a request type raises `HandlerAlreadyRegisteredError` against the first.
3. `pytest_markdown_docs_markdown_it` swaps in a parser that dedents fenced blocks first.
   Google convention indents an `Examples:` section's body, and CommonMark reads any block
   indented four spaces or more as an *indented* code block rather than a fence — so without
   this every docstring example is invisible to the collector. Dedenting is line-preserving,
   so reported failure line numbers still point at the real source line.

The cast is rebuilt per snippet, deliberately: `Request` subclasses register their response
type when the class statement executes, so sharing one set of classes across snippets would
resurrect the cross-page collisions the registry reset exists to prevent.
"""

import re
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, override

import pytest
from markdown_it import MarkdownIt
from markdown_it.token import Token

import pymediate
import pymediate.sync
from pymediate._internal.registry import clear_all_registries

_FENCE_OPEN = re.compile(r"^(?P<indent>[ \t]+)(?:`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^(?:`{3,}|~{3,})\s*$")


def _dedent_fenced_blocks(text: str) -> str:
    """Strip each fenced block's own indentation, leaving every other line untouched.

    A fence indented four spaces or more — which is every fence inside a Google-convention
    `Examples:` section — parses as an indented code block, so the collector never sees it.
    The rewrite is line-for-line, keeping reported line numbers pointed at the real source.

    Args:
        text: The markdown or cleaned-up docstring to normalize.

    Returns:
        The same text with indented fenced blocks moved out to the left margin.
    """
    out: list[str] = []
    indent: str | None = None
    for line in text.splitlines():
        if indent is None:
            match = _FENCE_OPEN.match(line)
            indent = match["indent"] if match else None
            out.append(line[len(indent) :] if indent else line)
            continue
        stripped = line[len(indent) :] if line.startswith(indent) else line.lstrip()
        out.append(stripped)
        if _FENCE_CLOSE.match(stripped):
            indent = None
    return "\n".join(out)


class _DedentingMarkdownIt(MarkdownIt):
    """A CommonMark parser that dedents fenced blocks before parsing them."""

    def parse(self, src: str, env: Any = None) -> list[Token]:
        """Parse the source with its fenced blocks pulled out to the left margin.

        Args:
            src: The markdown or docstring source.
            env: The parser environment, forwarded unchanged.

        Returns:
            The parsed token stream.
        """
        return super().parse(_dedent_fenced_blocks(src), {} if env is None else env)


@pytest.hookimpl(tryfirst=True)
def pytest_markdown_docs_markdown_it() -> MarkdownIt:
    """Supply the dedenting parser in place of pytest-markdown-docs' default.

    CommonMark's HTML-block rule is disabled because the docs are MDX, not HTML: a line like
    `</Tab>` opens an HTML block that runs to the next blank line, swallowing the fence right
    below it. Left on, every `<Tabs>`-wrapped example — the whole async/sync half of the API
    reference — is silently skipped rather than reported as uncovered.

    Returns:
        The parser used to find code fences in every collected file.
    """
    return _DedentingMarkdownIt(config="commonmark").disable("html_block")


# Names every snippet gets for free: the public API of both mirror sides plus the stdlib
# imports the examples lean on. Snippets that import these explicitly (most do) simply
# rebind the same objects, so seeding them changes nothing for those blocks.
_STATIC_GLOBALS: dict[str, Any] = {
    "pymediate": pymediate,
    "sync": pymediate.sync,
    "dataclass": dataclass,
    "field": field,
    "Any": Any,
    "Protocol": Protocol,
    "override": override,
    "AsyncIterator": AsyncIterator,
    "Iterator": Iterator,
    "Sequence": Sequence,
    **{name: getattr(pymediate, name) for name in pymediate.__all__},
}


_current_cast: dict[str, Any] = {}


def _example_cast() -> dict[str, Any]:
    """Build a fresh instance of the recurring order-domain cast.

    These are the names the documentation's fragments use without redefining them on every
    page — the Shop's messages, the collaborators handlers receive, and the behaviors the
    pipeline examples wrap requests with. A page that defines its own version of any of them
    simply shadows the one seeded here.

    Rebuilt per snippet because defining a `Request`, `StreamRequest`, or `Notification`
    subclass registers it; reusing one set of classes would leak registrations between
    snippets. Nothing here registers a *handler* — see the fixtures below for why.

    Returns:
        The example classes, keyed by the name the documentation uses for them.
    """

    @dataclass(frozen=True)
    class OrderReceipt:
        order_id: int
        summary: str

    @dataclass(frozen=True)
    class OrderDetails:
        order_id: int
        item: str
        quantity: int

    @dataclass(frozen=True)
    class PlaceOrder(pymediate.Request[OrderReceipt]):
        customer_id: int
        item: str
        quantity: int

    @dataclass(frozen=True)
    class ExportOrders(pymediate.StreamRequest[bytes]):
        customer_id: int

    @dataclass(frozen=True)
    class OrderPlaced(pymediate.Notification):
        order_id: int
        item: str

    class OrderStore(Protocol):
        async def add(self, request: PlaceOrder) -> int: ...

    class PostgresOrderStore:
        async def add(self, request: PlaceOrder) -> int:
            return 42

    class InMemoryOrderStore:
        async def add(self, request: PlaceOrder) -> int:
            return 42

    class Inventory(Protocol):
        async def available(self, item: str) -> int | None: ...

    class RequestLogging(pymediate.PipelineBehavior[pymediate.Request[Any]]):
        @override
        async def __call__(self, request: pymediate.Request[Any], next: pymediate.Next[Any]) -> Any:
            return await next()

    class LoggingBehavior(pymediate.PipelineBehavior[pymediate.Request[Any]]):
        @override
        async def __call__(self, request: pymediate.Request[Any], next: pymediate.Next[Any]) -> Any:
            return await next()

    class ValidatePlaceOrder(pymediate.PipelineBehavior[PlaceOrder]):
        @override
        async def __call__(self, request: PlaceOrder, next: pymediate.Next[Any]) -> Any:
            return await next()

    return {
        "OrderReceipt": OrderReceipt,
        "OrderDetails": OrderDetails,
        "PlaceOrder": PlaceOrder,
        "ExportOrders": ExportOrders,
        "OrderPlaced": OrderPlaced,
        "OrderStore": OrderStore,
        "PostgresOrderStore": PostgresOrderStore,
        "InMemoryOrderStore": InMemoryOrderStore,
        "Inventory": Inventory,
        "RequestLogging": RequestLogging,
        "LoggingBehavior": LoggingBehavior,
        "ValidatePlaceOrder": ValidatePlaceOrder,
    }


def pytest_markdown_docs_globals() -> dict[str, Any]:
    """Seed each documentation snippet with the shared example cast.

    Returns:
        The globals the snippet executes against.
    """
    return _STATIC_GLOBALS | _current_cast


# The two fixtures below stand in for setup a page describes in prose but does not show — the
# handler instance behind `Services(PlaceOrderHandler())`, and an already-built mediator. A
# fence opts in by name, `{/* pmd-metadata: fixture:mediator */}`, and pytest-markdown-docs
# binds the fixture's value to its own name in that fence's globals.
#
# They are fixtures rather than part of the cast precisely because they must be opt-in: a
# registered handler in every snippet's globals would collide with the pages whose subject is
# *defining* a handler for `PlaceOrder`, which is exactly what `HandlerAlreadyRegisteredError`
# is there to catch.


@pytest.fixture
def PlaceOrderHandler() -> type[Any]:  # noqa: N802 - bound into snippet globals under this name
    """Build and register the request handler the documentation's examples assume.

    The `orders` parameter is optional so the same class satisfies both the bare
    `Services(PlaceOrderHandler())` of the mediator pages and the
    `providers.Factory(PlaceOrderHandler, orders=order_store)` of the dependency-injection
    guide.

    Returns:
        A handler class registered for this snippet's `PlaceOrder`.
    """
    place_order = _current_cast["PlaceOrder"]
    order_receipt = _current_cast["OrderReceipt"]

    class PlaceOrderHandler(pymediate.RequestHandler[place_order]):  # type: ignore[valid-type]
        def __init__(self, orders: Any = None) -> None:
            self._orders = orders

        # The annotations have to be the cast's own classes, and they have to be right when
        # the class statement runs — PyMediate validates them from __init_subclass__.
        @override
        async def __call__(self, request: place_order) -> order_receipt:  # type: ignore[valid-type]
            order: Any = request
            summary = f"{order.quantity} × {order.item}"
            return order_receipt(order_id=42, summary=summary)  # type: ignore[no-any-return]

    return PlaceOrderHandler


@pytest.fixture
def mediator(PlaceOrderHandler: type[Any]) -> pymediate.Mediator:  # noqa: N803
    """Build the mediator the documentation's fragments dispatch through.

    Carries a stream handler as well as the request handler, so `stream()` fragments resolve.
    `publish()` fragments need nothing extra — a notification with no subscribers is valid.

    Args:
        PlaceOrderHandler: The registered handler class, supplied by its own fixture.

    Returns:
        A mediator whose provider holds an instance of each handler.
    """
    export_orders = _current_cast["ExportOrders"]

    class ExportOrdersHandler(pymediate.StreamRequestHandler[export_orders]):  # type: ignore[valid-type]
        @override
        async def __call__(self, request: export_orders) -> AsyncIterator[bytes]:  # type: ignore[valid-type]
            yield b"order_id,total_pence\n"
            yield b"42,2500\n"

    return pymediate.Mediator(pymediate.Services(PlaceOrderHandler(), ExportOrdersHandler()))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Build this snippet's example cast before anything else can reach for it.

    Runs ahead of fixture resolution, which happens during item setup, so the `mediator` and
    `PlaceOrderHandler` fixtures below and the globals hook all close over the same classes.

    Args:
        item: The item about to run; non-snippet items are left alone.
    """
    global _current_cast
    if item.get_closest_marker("markdown-docs") is not None:
        _current_cast = _example_cast()


def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Clear the process-global registries after each documentation snippet.

    Teardown rather than an autouse fixture, deliberately: pytest-markdown-docs calls the
    globals hook *before* it resolves an item's fixtures, so a fixture clearing on the way in
    would wipe the registrations the cast just made. Clearing on the way out isolates the next
    snippet just as well, since teardown precedes the next item's setup.

    Args:
        item: The item that just ran; non-snippet items are left alone.
    """
    if item.get_closest_marker("markdown-docs") is not None:
        clear_all_registries()
