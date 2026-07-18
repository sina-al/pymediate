"""Dependency bindings owned by the orders feature module.

Dependency Injector accepts runtime-checkable protocols for ``instance_of`` at runtime,
while its type stub requires a concrete class. This file is exclusively declarative bindings.
"""

from typing import Protocol, runtime_checkable

from dependency_injector import containers, providers

from shop.application.orders.cancel_order import CancelOrderHandler
from shop.application.orders.create_order import CreateOrderHandler
from shop.application.orders.export_orders import ExportOrdersHandler
from shop.application.orders.get_order_history import GetOrderHistoryHandler
from shop.application.orders.refund_order import RefundOrderHandler
from shop.application.orders.request_order_export import RequestOrderExportHandler
from shop.application.orders.send_order_confirmation import SendOrderConfirmationHandler
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.cancel_order import (
    CancelOrderDbGateway,
    CancelOrderInventory,
    CancelOrderMailer,
    CancelOrderPaymentGateway,
)
from shop.ports.orders.create_order import (
    CreateOrderClock,
    CreateOrderDbGateway,
    CreateOrderInventory,
    CreateOrderPaymentGateway,
    ProductCatalogue,
)
from shop.ports.orders.export_orders import (
    ExportOrdersDbGateway,
    ExportOrdersMailer,
    ExportOrdersStorage,
)
from shop.ports.orders.refund_order import (
    RefundOrderDbGateway,
    RefundOrderMailer,
    RefundOrderPaymentGateway,
)
from shop.ports.orders.request_order_export import RequestOrderExportDbGateway
from shop.ports.orders.send_order_confirmation import SendOrderConfirmationMailer
from shop.ports.unit_of_work import UnitOfWork


@runtime_checkable
class OrdersDbGateway(
    CreateOrderDbGateway,
    CancelOrderDbGateway,
    RefundOrderDbGateway,
    ExportOrdersDbGateway,
    RequestOrderExportDbGateway,
    Protocol,
):
    """Aggregate only the persistence operations used by the orders feature module."""


class OrdersContainer(containers.DeclarativeContainer):
    """Bind every order handler to its own narrow outbound ports."""

    # Outbound ports
    catalogue = providers.Dependency(instance_of=ProductCatalogue)
    clock = providers.Dependency(instance_of=CreateOrderClock)
    database = providers.Dependency(instance_of=OrdersDbGateway)
    journal = providers.Dependency(instance_of=DomainEventJournal)
    unit = providers.Dependency(instance_of=UnitOfWork)
    create_inventory = providers.Dependency(instance_of=CreateOrderInventory)
    create_payments = providers.Dependency(instance_of=CreateOrderPaymentGateway)
    confirmation_mailer = providers.Dependency(instance_of=SendOrderConfirmationMailer)
    cancel_inventory = providers.Dependency(instance_of=CancelOrderInventory)
    cancel_payments = providers.Dependency(instance_of=CancelOrderPaymentGateway)
    cancel_mailer = providers.Dependency(instance_of=CancelOrderMailer)
    refund_payments = providers.Dependency(instance_of=RefundOrderPaymentGateway)
    refund_mailer = providers.Dependency(instance_of=RefundOrderMailer)
    storage = providers.Dependency(instance_of=ExportOrdersStorage)
    export_mailer = providers.Dependency(instance_of=ExportOrdersMailer)

    # Request handlers
    create_order = providers.Factory(
        CreateOrderHandler,
        catalogue=catalogue,
        clock=clock,
        unit=unit,
        database=database,
        inventory=create_inventory,
        payments=create_payments,
        journal=journal,
    )
    cancel_order = providers.Factory(
        CancelOrderHandler,
        unit=unit,
        database=database,
        inventory=cancel_inventory,
        payments=cancel_payments,
        mailer=cancel_mailer,
        journal=journal,
    )
    refund_order = providers.Factory(
        RefundOrderHandler,
        unit=unit,
        database=database,
        payments=refund_payments,
        mailer=refund_mailer,
        journal=journal,
    )
    export_orders = providers.Factory(
        ExportOrdersHandler,
        database=database,
        storage=storage,
        mailer=export_mailer,
    )
    get_order_history = providers.Factory(GetOrderHistoryHandler, journal=journal)
    request_order_export = providers.Factory(
        RequestOrderExportHandler, unit=unit, database=database, journal=journal
    )
    send_order_confirmation = providers.Factory(
        SendOrderConfirmationHandler, mailer=confirmation_mailer
    )
