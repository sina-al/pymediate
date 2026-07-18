"""Dependency bindings owned by the invoices feature module.

Dependency Injector accepts runtime-checkable protocols for ``instance_of`` at runtime,
while its type stub requires a concrete class. This file is exclusively declarative bindings.
"""

from typing import Protocol, runtime_checkable

from dependency_injector import containers, providers

from shop.application.invoices.create_invoice import CreateInvoiceHandler
from shop.application.invoices.get_invoice import GetInvoiceHandler
from shop.ports.audit import DomainEventJournal
from shop.ports.invoices.create_invoice import (
    CreateInvoiceDbGateway,
    CreateInvoiceRenderer,
    CreateInvoiceStorage,
)
from shop.ports.invoices.get_invoice import GetInvoiceDbGateway
from shop.ports.unit_of_work import UnitOfWork


@runtime_checkable
class InvoicesDbGateway(CreateInvoiceDbGateway, GetInvoiceDbGateway, Protocol):
    """Aggregate only the persistence operations used by the invoices feature module."""


class InvoicesContainer(containers.DeclarativeContainer):
    """Bind invoice handlers to persistence and document rendering."""

    # Outbound ports
    database = providers.Dependency(instance_of=InvoicesDbGateway)
    unit = providers.Dependency(instance_of=UnitOfWork)
    journal = providers.Dependency(instance_of=DomainEventJournal)
    renderer = providers.Dependency(instance_of=CreateInvoiceRenderer)
    storage = providers.Dependency(instance_of=CreateInvoiceStorage)
    create_invoice = providers.Factory(
        CreateInvoiceHandler,
        unit=unit,
        database=database,
        renderer=renderer,
        storage=storage,
        journal=journal,
    )
    get_invoice = providers.Factory(GetInvoiceHandler, database=database)
