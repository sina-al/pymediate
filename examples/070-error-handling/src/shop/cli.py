"""CLI edge: the *same* core, mapping the *same* domain errors to exit codes.

This is the proof that keeping transport out of the core pays off. There is no HTTP here —
no request, no client, nothing a 404 could be sent to. The core raised the very same
``ProductNotFoundError`` it raises for the web edge; this layer decides that means exit
code 3. Only this mapping differs between the two transports; the core is byte-for-byte the
same.

``send_as_cli`` is the mapping, factored out so a test can drive it directly. It catches
domain errors and turns them into exit codes — and *only* domain errors, which is exactly
why a handler that leaks a framework exception (see ``leaky.py``) breaks it.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from pymediate import Mediator, Request

from .core import GetProduct, OutOfStockError, PlaceOrder, ProductNotFoundError, build_mediator

EXIT_OK = 0
EXIT_NOT_FOUND = 3
EXIT_OUT_OF_STOCK = 4


def send_as_cli(mediator: Mediator, request: Request[object]) -> int:
    """Dispatch a request and translate domain errors into process exit codes.

    Note what it catches: ``ProductNotFoundError`` and ``OutOfStockError`` — domain errors.
    Anything else (including a leaked ``HTTPException``) is not the CLI's to interpret and
    escapes, crashing the process. That's the failure mode the anti-pattern triggers.
    """
    try:
        result = asyncio.run(mediator.send(request))
    except ProductNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_NOT_FOUND
    except OutOfStockError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_OUT_OF_STOCK
    print(result)
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``get <id>`` / ``order <id> <qty>`` and dispatch through the core."""
    parser = argparse.ArgumentParser(prog="shop-cli", description="Shop CLI over the same core.")
    sub = parser.add_subparsers(dest="command", required=True)

    get_parser = sub.add_parser("get", help="fetch a product")
    get_parser.add_argument("product_id", type=int)

    order_parser = sub.add_parser("order", help="order a product")
    order_parser.add_argument("product_id", type=int)
    order_parser.add_argument("quantity", type=int)

    args = parser.parse_args(argv)
    mediator = build_mediator()

    if args.command == "get":
        return send_as_cli(mediator, GetProduct(product_id=args.product_id))
    return send_as_cli(mediator, PlaceOrder(product_id=args.product_id, quantity=args.quantity))


def run() -> None:
    """Console-script entry point (``uv run shop-cli``)."""
    sys.exit(main())


if __name__ == "__main__":
    run()
