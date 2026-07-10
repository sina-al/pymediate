"""The memory variant's web process: Flask plus an in-process export worker."""

import logging
import threading

from flask import Flask

from shop_delivery.web import create_app, serve
from shop_delivery.worker import drain_memory_queue

from .wiring import build


def make_app() -> Flask:
    """Build the app and start the export consumer thread beside it.

    In-memory persistence lives and dies with this process, so the worker must too —
    a separate worker container would export from an empty store.
    """
    mediator, jobs = build()
    threading.Thread(
        target=drain_memory_queue, args=(mediator, jobs.jobs), daemon=True, name="export-worker"
    ).start()
    return create_app(mediator, jobs)


def main() -> None:
    """Entry point for the `shop-web` script."""
    logging.basicConfig(level=logging.INFO)
    serve(make_app())


if __name__ == "__main__":
    main()
