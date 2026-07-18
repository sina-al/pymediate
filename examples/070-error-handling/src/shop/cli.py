"""Map shop domain errors to CLI exit codes.

The CLI has no HTTP response, so it maps ``ProductNotFoundError`` to exit
code 3 instead of status 404. The core is shared by both interfaces.

``send_as_cli`` is separated so tests can call the mapping directly. An HTTP-specific exception
is not one of the domain errors it handles; ``leaky.py`` demonstrates that mismatch.
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

    It catches ``ProductNotFoundError`` and ``OutOfStockError``, which are domain errors.
    Other exceptions, including ``HTTPException``, propagate because the CLI mapping
    has no rule for them.
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
