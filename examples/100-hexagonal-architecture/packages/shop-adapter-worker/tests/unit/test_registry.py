"""Verify stable integration contracts decode into typed mediator requests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError
from pymediate import Request

from shop.application.integration_contracts import (
    InvoiceRequestedV1,
    OrderConfirmationRequestedV1,
    OrderExportRequestedV1,
)
from shop.application.invoices.create_invoice import CreateInvoiceRequest
from shop.application.orders.export_orders import ExportOrdersRequest
from shop.application.orders.send_order_confirmation import SendOrderConfirmationRequest
from shop.ports.integration import IntegrationMessage, JsonObject
from shop.worker.registry import MessageDecoder, MessageRegistry, decode_message


def message(event_type: str, payload: dict[str, object], version: int = 1) -> IntegrationMessage:
    return IntegrationMessage(
        "12345678-1234-5678-1234-567812345678",
        event_type,
        version,
        datetime(2026, 7, 15, tzinfo=UTC),
        cast("JsonObject", payload),
    )


def test_registry_decodes_each_supported_contract() -> None:
    # Arrange
    message_id = "12345678-1234-5678-1234-567812345678"
    placed_message = message(
        OrderConfirmationRequestedV1.event_type, {"order_id": 1, "customer_id": 7}
    )
    export_message = message(OrderExportRequestedV1.event_type, {"customer_id": 7, "format": "csv"})
    invoice_message = message(
        InvoiceRequestedV1.event_type,
        {"order_id": 1, "customer_id": 7, "total_pence": 1500},
    )

    # Act
    placed = decode_message(placed_message)
    export = decode_message(export_message)
    invoice = decode_message(invoice_message)

    # Assert
    assert placed == SendOrderConfirmationRequest(1, 7, message_id)
    assert export == ExportOrdersRequest(7, "csv", message_id)
    assert invoice == CreateInvoiceRequest(1, 7, 1500, message_id)


def test_registry_rejects_unknown_contract_version() -> None:
    # Arrange
    unknown = message(OrderConfirmationRequestedV1.event_type, {}, version=2)

    # Act
    with pytest.raises(ValueError, match="shop.orders.order-confirmation-requested v2"):
        decode_message(unknown)

    # Assert
    assert unknown.schema_version == 2


def test_registry_rejects_malformed_known_payload() -> None:
    # Arrange
    malformed = message(OrderConfirmationRequestedV1.event_type, {"customer_id": 7})

    # Act
    with pytest.raises(ValidationError):
        decode_message(malformed)

    # Assert
    assert malformed.payload == {"customer_id": 7}


def test_registry_does_not_coerce_wire_values() -> None:
    # Arrange
    malformed = message(
        OrderConfirmationRequestedV1.event_type,
        {"order_id": "1", "customer_id": 7},
    )

    # Act
    with pytest.raises(ValidationError):
        decode_message(malformed)

    # Assert
    assert malformed.payload["order_id"] == "1"


@dataclass(frozen=True)
class CustomerRenamedV1Request(Request[None]):
    customer_id: int
    name: str


@dataclass(frozen=True)
class CustomerRenamedV2Request(Request[None]):
    customer_id: int
    given_name: str
    family_name: str


def test_registry_can_evolve_one_event_type_with_explicit_version_decoders() -> None:
    # Arrange
    def decode_v1(envelope: IntegrationMessage) -> Request[Any]:
        return CustomerRenamedV1Request(
            cast("int", envelope.payload["customer_id"]),
            cast("str", envelope.payload["name"]),
        )

    def decode_v2(envelope: IntegrationMessage) -> Request[Any]:
        return CustomerRenamedV2Request(
            cast("int", envelope.payload["customer_id"]),
            cast("str", envelope.payload["given_name"]),
            cast("str", envelope.payload["family_name"]),
        )

    registry = MessageRegistry(
        cast(
            "dict[tuple[str, int], MessageDecoder]",
            {
                ("example.customers.customer-renamed", 1): decode_v1,
                ("example.customers.customer-renamed", 2): decode_v2,
            },
        )
    )
    version_one = message(
        "example.customers.customer-renamed",
        {"customer_id": 7, "name": "Ada Lovelace"},
        version=1,
    )
    version_two = message(
        "example.customers.customer-renamed",
        {"customer_id": 7, "given_name": "Ada", "family_name": "Lovelace"},
        version=2,
    )

    # Act
    first = registry.decode(version_one)
    second = registry.decode(version_two)

    # Assert
    assert first == CustomerRenamedV1Request(7, "Ada Lovelace")
    assert second == CustomerRenamedV2Request(7, "Ada", "Lovelace")
