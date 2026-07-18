"""Capture integration events and trace metadata for the transactional outbox."""

from opentelemetry.propagate import inject

from shop.ports.integration import IntegrationEvent, IntegrationMessage
from shop.ports.outbox import OutboxMessage


def outbox_message(event: IntegrationEvent) -> OutboxMessage:
    """Envelope one integration event and capture its separate W3C trace carrier."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return OutboxMessage(IntegrationMessage.from_event(event), carrier)
