"""Transactional boundary that moves exports out of the request cycle."""

from typing import Protocol, runtime_checkable

from shop.ports.outbox import OutboxWriter


@runtime_checkable
class RequestOrderExportDbGateway(OutboxWriter, Protocol):
    """Persist the export event in the caller's transaction."""
