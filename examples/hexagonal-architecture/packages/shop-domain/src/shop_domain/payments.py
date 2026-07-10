"""Payments: the record a refund leaves behind."""

from dataclasses import dataclass
from enum import StrEnum


class RefundMethod(StrEnum):
    """How a refund was issued."""

    ORIGINAL_PAYMENT = "original_payment"
    STORE_CREDIT = "store_credit"


@dataclass
class Refund:
    """The outcome of refunding an order."""

    order_id: str
    amount_cents: int
    method: RefundMethod
    reference: str
