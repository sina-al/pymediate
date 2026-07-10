"""The neo4j variant's export worker process."""

import logging

from shop_delivery.worker import run_redis_worker

from .wiring import redis_client, runtime


def main() -> None:
    """Entry point for the `shop-worker` script."""
    logging.basicConfig(level=logging.INFO)
    with runtime() as mediator:
        run_redis_worker(mediator, redis_client())


if __name__ == "__main__":
    main()
