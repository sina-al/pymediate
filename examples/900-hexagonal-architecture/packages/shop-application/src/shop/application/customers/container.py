"""Dependency bindings owned by the customers feature module.

Dependency Injector accepts runtime-checkable protocols for ``instance_of`` at runtime,
while its type stub requires a concrete class. This file is exclusively declarative bindings.
"""

from typing import Protocol, runtime_checkable

from dependency_injector import containers, providers

from shop.application.customers.adjust_store_credit import AdjustStoreCreditHandler
from shop.application.customers.close_customer_account import CloseCustomerAccountHandler
from shop.application.customers.open_customer_account import OpenCustomerAccountHandler
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.adjust_store_credit import AdjustStoreCreditDbGateway
from shop.ports.customers.close_customer_account import (
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
)
from shop.ports.customers.open_customer_account import OpenCustomerAccountDbGateway
from shop.ports.unit_of_work import UnitOfWork


@runtime_checkable
class CustomersDbGateway(
    OpenCustomerAccountDbGateway,
    AdjustStoreCreditDbGateway,
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
    Protocol,
):
    """Aggregate only the persistence operations used by the customers feature module."""


class CustomersContainer(containers.DeclarativeContainer):
    """Bind customer handlers to the ports each workflow actually needs."""

    # Outbound ports
    database = providers.Dependency(instance_of=CustomersDbGateway)
    unit = providers.Dependency(instance_of=UnitOfWork)
    journal = providers.Dependency(instance_of=DomainEventJournal)

    # Request handlers
    open_customer_account = providers.Factory(
        OpenCustomerAccountHandler, unit=unit, database=database, journal=journal
    )
    adjust_store_credit = providers.Factory(
        AdjustStoreCreditHandler, unit=unit, database=database, journal=journal
    )
    close_customer_account = providers.Factory(
        CloseCustomerAccountHandler,
        unit=unit,
        database=database,
        orders=database,
        journal=journal,
    )
