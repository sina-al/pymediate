"""The wired application: bootstrap + audit behavior, end to end on fakes."""

from shop_adapter_memory.repositories import MemoryCustomerRepository, MemoryOrderRepository
from shop_adapter_memory.services import (
    LocalFileStorage,
    LoggingAuditLog,
    RecordingMailer,
    RecordingPaymentGateway,
)
from shop_core.bootstrap import build_mediator
from shop_core.customers import RegisterCustomer
from shop_core.orders import PlaceOrder
from shop_domain.orders import LineItem


def test_every_dispatched_request_is_audited(tmp_path: object) -> None:
    audit = LoggingAuditLog()
    mediator = build_mediator(
        orders=MemoryOrderRepository(),
        customers=MemoryCustomerRepository(),
        payments=RecordingPaymentGateway(),
        mailer=RecordingMailer(),
        storage=LocalFileStorage(str(tmp_path)),
        audit=audit,
    )

    customer = mediator.send(RegisterCustomer(name="Ada", email="ada@example.com"))
    mediator.send(
        PlaceOrder(
            customer_id=customer.customer_id,
            items=[LineItem(sku="widget", quantity=1, unit_price_cents=500)],
        )
    )

    assert audit.events == ["RegisterCustomer", "PlaceOrder"]
