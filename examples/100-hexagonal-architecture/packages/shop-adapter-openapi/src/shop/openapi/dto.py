"""Pydantic HTTP contracts, deliberately namespaced from application contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HttpModel(BaseModel):
    """Reject fields that are not part of the documented HTTP contract."""

    model_config = ConfigDict(extra="forbid")


class OpenCustomerAccountRequest(HttpModel):
    """HTTP body for opening a customer account."""

    customer_id: int = Field(gt=0, examples=[7])


class OpenCustomerAccountResponse(HttpModel):
    """HTTP representation of a newly opened customer account."""

    customer_id: int
    store_credit_pence: int


class OrderItemRequest(HttpModel):
    """One product supplied by an HTTP caller."""

    sku: str = Field(min_length=1, examples=["book"])
    quantity: int = Field(gt=0, examples=[2])


class CreateOrderRequest(HttpModel):
    """HTTP body for placing an order."""

    customer_id: int = Field(gt=0, examples=[7])
    items: list[OrderItemRequest] = Field(min_length=1)


class CreateOrderResponse(HttpModel):
    """HTTP representation of a created order."""

    order_id: int
    customer_id: int
    total_pence: int
    refunded_pence: int
    status: str


class RefundOrderRequest(HttpModel):
    """HTTP body for refunding an order."""

    amount_pence: int = Field(gt=0, examples=[900])


class RefundOrderResponse(CreateOrderResponse):
    """HTTP representation of a refunded order."""


class CancelOrderResponse(CreateOrderResponse):
    """HTTP representation of a cancelled order."""


class RequestOrderExportResponse(HttpModel):
    """HTTP representation of an accepted background export."""

    job_id: str
    customer_id: int


class GetInvoiceResponse(HttpModel):
    """HTTP representation of a public invoice result."""

    invoice_id: int
    order_id: int
    customer_id: int
    total_pence: int
    document_url: str


class CreateMonthlyStatementRequest(HttpModel):
    """HTTP body for requesting a monthly statement."""

    year: int = Field(ge=2000, le=2100, examples=[2026])
    month: int = Field(ge=1, le=12, examples=[7])
    currency: str = Field(pattern="^(GBP|EUR|USD)$", examples=["EUR"])


class CreateMonthlyStatementResponse(HttpModel):
    """HTTP representation of a created monthly statement."""

    statement_id: int
    customer_id: int
    year: int
    month: int
    currency: str
    order_count: int
    total_minor: int
    document_url: str


class AdjustStoreCreditRequest(HttpModel):
    """HTTP body for adding customer store credit."""

    amount_pence: int = Field(gt=0, examples=[1500])


class AdjustStoreCreditResponse(HttpModel):
    """HTTP representation of the resulting customer balance."""

    customer_id: int
    store_credit_pence: int


class OrderHistoryEntryResponse(HttpModel):
    """Allowlisted HTTP representation of one order fact."""

    event_id: str
    kind: Literal["placed", "refunded", "cancelled"]
    occurred_at: datetime
    amount_pence: int | None = None
    refunded_pence: int | None = None
    status: str | None = None


class GetOrderHistoryResponse(HttpModel):
    """Safe public history for one order."""

    order_id: int
    entries: list[OrderHistoryEntryResponse]


class ProblemDetailsResponse(HttpModel):
    """RFC 9457 problem document returned for a translated domain error."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    context: dict[str, object]
