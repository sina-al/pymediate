"""The postgres variant's web process."""

import logging
from contextlib import ExitStack

from shop_delivery.web import create_app, serve

from .wiring import job_queue, runtime


def main() -> None:
    """Entry point for the `shop-web` script."""
    logging.basicConfig(level=logging.INFO)
    with ExitStack() as stack:
        mediator = stack.enter_context(runtime())
        serve(create_app(mediator, job_queue()))


if __name__ == "__main__":
    main()
