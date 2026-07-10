"""Choose the adapters, hand them to the core, get back a mediator."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import redis
from pymediate import Mediator

from shop_adapter_memory.services import (
    LocalFileStorage,
    LoggingAuditLog,
    RecordingMailer,
    RecordingPaymentGateway,
)
from shop_adapter_neo4j.repositories import (
    Neo4jCustomerRepository,
    Neo4jOrderRepository,
    create_driver,
)
from shop_core.bootstrap import build_mediator
from shop_delivery.worker import RedisJobQueue


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


def job_queue() -> RedisJobQueue:
    return RedisJobQueue(redis_client())


@contextmanager
def runtime() -> Iterator[Mediator]:
    """Open the driver, wire the application, close the driver on the way out."""
    driver = create_driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        os.environ.get("NEO4J_USER", "neo4j"),
        os.environ.get("NEO4J_PASSWORD", "shopshop"),
    )
    try:
        yield build_mediator(
            orders=Neo4jOrderRepository(driver),
            customers=Neo4jCustomerRepository(driver),
            payments=RecordingPaymentGateway(),
            mailer=RecordingMailer(),
            storage=LocalFileStorage(os.environ.get("EXPORT_DIR", "/tmp/shop-exports")),
            audit=LoggingAuditLog(),
        )
    finally:
        driver.close()
