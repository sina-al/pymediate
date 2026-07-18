"""Explicit integration-contract to mediator-request translations."""

from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pymediate import Request

from shop.application.integration_contracts import (
    InvoiceRequestedV1,
    OrderConfirmationRequestedV1,
    OrderExportRequestedV1,
)
from shop.application.invoices.create_invoice import CreateInvoiceRequest
from shop.application.orders.export_orders import ExportOrdersRequest
from shop.application.orders.send_order_confirmation import SendOrderConfirmationRequest
from shop.ports.integration import IntegrationMessage

type MessageDecoder = Callable[[IntegrationMessage], Request[Any]]


class _OrderConfirmationRequestedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    order_id: Annotated[int, Field(gt=0)]
    customer_id: Annotated[int, Field(gt=0)]


class _OrderExportRequestedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    customer_id: Annotated[int, Field(gt=0)]
    format: Literal["csv", "jsonl"]


class _InvoiceRequestedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    order_id: Annotated[int, Field(gt=0)]
    customer_id: Annotated[int, Field(gt=0)]
    total_pence: Annotated[int, Field(gt=0)]


def _decode_order_confirmation_requested(message: IntegrationMessage) -> Request[Any]:
    payload = _OrderConfirmationRequestedPayload.model_validate(message.payload)
    return SendOrderConfirmationRequest(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        idempotency_key=message.message_id,
    )


def _decode_order_export_requested(message: IntegrationMessage) -> Request[Any]:
    payload = _OrderExportRequestedPayload.model_validate(message.payload)
    return ExportOrdersRequest(
        customer_id=payload.customer_id,
        format=payload.format,
        idempotency_key=message.message_id,
    )


def _decode_invoice_requested(message: IntegrationMessage) -> Request[Any]:
    payload = _InvoiceRequestedPayload.model_validate(message.payload)
    return CreateInvoiceRequest(
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        total_pence=payload.total_pence,
        idempotency_key=message.message_id,
    )


DECODERS: dict[tuple[str, int], MessageDecoder] = {
    (
        OrderConfirmationRequestedV1.event_type,
        OrderConfirmationRequestedV1.schema_version,
    ): _decode_order_confirmation_requested,
    (InvoiceRequestedV1.event_type, InvoiceRequestedV1.schema_version): _decode_invoice_requested,
    (
        OrderExportRequestedV1.event_type,
        OrderExportRequestedV1.schema_version,
    ): _decode_order_export_requested,
}


class MessageRegistry:
    """Translate explicitly supported wire-contract versions into requests."""

    def __init__(self, decoders: Mapping[tuple[str, int], MessageDecoder]) -> None:
        self._decoders = dict(decoders)

    def decode(self, message: IntegrationMessage) -> Request[Any]:
        """Validate one known contract version and construct its mediator request."""
        key = (message.event_type, message.schema_version)
        try:
            decoder = self._decoders[key]
        except KeyError:
            raise ValueError(
                f"Unsupported integration message: {message.event_type} v{message.schema_version}"
            ) from None
        return decoder(message)


registry = MessageRegistry(DECODERS)


def decode_message(message: IntegrationMessage) -> Request[Any]:
    """Decode a message through the worker's explicit production registry."""
    return registry.decode(message)
