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
from shop_adapter_postgres.repositories import (
    PostgresCustomerRepository,
    PostgresOrderRepository,
    create_pool,
)
from shop_adapter_postgres.schema import ensure_schema
from shop_core.bootstrap import build_mediator
from shop_delivery.worker import RedisJobQueue


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://shop:shop@localhost:5432/shop")


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


def job_queue() -> RedisJobQueue:
    return RedisJobQueue(redis_client())


@contextmanager
def runtime() -> Iterator[Mediator]:
    """Open the pool, wire the application, close the pool on the way out."""
    pool = create_pool(database_url())
    try:
        ensure_schema(pool)
        yield build_mediator(
            orders=PostgresOrderRepository(pool),
            customers=PostgresCustomerRepository(pool),
            payments=RecordingPaymentGateway(),
            mailer=RecordingMailer(),
            storage=LocalFileStorage(os.environ.get("EXPORT_DIR", "/tmp/shop-exports")),
            audit=LoggingAuditLog(),
        )
    finally:
        pool.close()
