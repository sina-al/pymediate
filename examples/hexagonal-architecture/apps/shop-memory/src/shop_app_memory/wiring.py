"""Choose the adapters, hand them to the core, get back a mediator."""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from pymediate import Mediator

from shop_adapter_memory.repositories import MemoryCustomerRepository, MemoryOrderRepository
from shop_adapter_memory.services import (
    LocalFileStorage,
    LoggingAuditLog,
    MemoryJobQueue,
    RecordingMailer,
    RecordingPaymentGateway,
)
from shop_core.bootstrap import build_mediator


def build() -> tuple[Mediator, MemoryJobQueue]:
    """Wire the application on in-memory adapters."""
    mediator = build_mediator(
        orders=MemoryOrderRepository(),
        customers=MemoryCustomerRepository(),
        payments=RecordingPaymentGateway(),
        mailer=RecordingMailer(),
        storage=LocalFileStorage(os.environ.get("EXPORT_DIR", "/tmp/shop-exports")),
        audit=LoggingAuditLog(),
    )
    return mediator, MemoryJobQueue()


@contextmanager
def runtime() -> Iterator[Mediator]:
    """A mediator for one CLI invocation; in-memory adapters need no teardown."""
    mediator, _ = build()
    yield mediator
