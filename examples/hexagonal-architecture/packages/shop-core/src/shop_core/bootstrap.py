"""Wire the core: the one function that knows every use case in the application."""

from pymediate import Mediator, Services

from shop_ports.audit import AuditLog
from shop_ports.customers import CustomerRepository
from shop_ports.notifications import Mailer
from shop_ports.orders import OrderRepository
from shop_ports.payments import PaymentGateway
from shop_ports.storage import FileStorage

from .behaviors import AuditTrail
from .customers import GetCustomerHandler, RegisterCustomerHandler
from .orders import (
    CancelOrderHandler,
    ExportOrdersHandler,
    PlaceOrderHandler,
    RefundOrderHandler,
)


def build_mediator(
    *,
    orders: OrderRepository,
    customers: CustomerRepository,
    payments: PaymentGateway,
    mailer: Mailer,
    storage: FileStorage,
    audit: AuditLog,
) -> Mediator:
    """Assemble the application from port implementations.

    Callers (the composition roots in `apps/`) decide *which* implementations to pass;
    this function decides *what the application is*. It's the entire registration
    surface — a new use case means one new line here, and nowhere else.
    """
    services = Services()
    services.add(AuditTrail(audit))
    services.add(RegisterCustomerHandler(customers))
    services.add(GetCustomerHandler(customers))
    services.add(PlaceOrderHandler(orders, customers))
    services.add(CancelOrderHandler(orders))
    services.add(RefundOrderHandler(orders, customers, payments, mailer))
    services.add(ExportOrdersHandler(orders, storage))
    return Mediator(services.provider())
