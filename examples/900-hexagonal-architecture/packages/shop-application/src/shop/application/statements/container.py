"""Dependency bindings owned by the statements feature module.

Dependency Injector accepts runtime-checkable protocols for ``instance_of`` at runtime,
while its type stub requires a concrete class. This file is exclusively declarative bindings.
"""

from dependency_injector import containers, providers

from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementHandler,
)
from shop.ports.audit import DomainEventJournal
from shop.ports.statements.create_monthly_statement import (
    CreateMonthlyStatementDbGateway,
    MonthlyStatementRenderer,
    MonthlyStatementStorage,
    StatementExchangeRates,
)
from shop.ports.unit_of_work import UnitOfWork


class StatementsContainer(containers.DeclarativeContainer):
    """Bind monthly statements to data, rates, rendering, and storage."""

    # Outbound ports
    database = providers.Dependency(instance_of=CreateMonthlyStatementDbGateway)
    unit = providers.Dependency(instance_of=UnitOfWork)
    journal = providers.Dependency(instance_of=DomainEventJournal)
    rates = providers.Dependency(instance_of=StatementExchangeRates)
    renderer = providers.Dependency(instance_of=MonthlyStatementRenderer)
    storage = providers.Dependency(instance_of=MonthlyStatementStorage)
    # Request handlers
    create_monthly_statement = providers.Factory(
        CreateMonthlyStatementHandler,
        unit=unit,
        database=database,
        rates=rates,
        renderer=renderer,
        storage=storage,
        journal=journal,
    )
