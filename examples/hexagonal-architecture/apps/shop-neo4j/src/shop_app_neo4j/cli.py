"""The neo4j variant's CLI entry point."""

import logging

from shop_delivery.cli import build_cli

from .wiring import runtime


def main() -> None:
    """Entry point for the `shop` script."""
    logging.basicConfig(level=logging.WARNING)
    build_cli(runtime)()


if __name__ == "__main__":
    main()
