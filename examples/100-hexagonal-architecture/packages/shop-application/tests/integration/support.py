"""Shared application-test harness built from zero-infrastructure YAML wiring."""

from dataclasses import dataclass
from datetime import date
from typing import cast

from pymediate import Mediator

from shop.adapters.ephemeral import (
    ConsoleMailer,
    EphemeralInventory,
    EphemeralPayments,
    EphemeralStorage,
    SqliteDbGateway,
    SqliteUnitOfWork,
)
from shop.application.container import ApplicationContainer
from shop.bindings.loading import create_application_container
from shop.bindings.wiring import Wiring
from shop.domain.entities.orders import Order, OrderLine
from shop.domain.events.base import AggregateType
from shop.ports.audit import DomainEventRecord


@dataclass(frozen=True)
class ApplicationHarness:
    """Expose the real mediator plus observable local adapter state."""

    container: ApplicationContainer
    mediator: Mediator
    database: SqliteDbGateway
    storage: EphemeralStorage
    inventory: EphemeralInventory
    payments: EphemeralPayments
    mailer: ConsoleMailer

    @classmethod
    def create(cls, wiring: Wiring) -> "ApplicationHarness":
        """Build the application from providers activated by the fixture."""
        container = create_application_container(wiring)
        return cls(
            container=container,
            mediator=container.mediator(),
            database=cast("SqliteDbGateway", container.database()),
            storage=cast("EphemeralStorage", container.storage()),
            inventory=cast("EphemeralInventory", container.inventory()),
            payments=cast("EphemeralPayments", container.payments()),
            mailer=cast("ConsoleMailer", container.mailer()),
        )

    async def seed_order(
        self,
        order_id: int = 1,
        customer_id: int = 7,
        lines: tuple[OrderLine, ...] = (OrderLine("book", 2, 1_500),),
        placed_on: date = date(2026, 7, 13),
    ) -> Order:
        """Arrange persisted state without exercising an unrelated use case."""
        order = Order.place(order_id, customer_id, lines, placed_on)
        async with SqliteUnitOfWork(self.database):
            await self.database.insert_order(order)
        return order

    async def events(
        self, aggregate_type: AggregateType, aggregate_id: int | str
    ) -> tuple[DomainEventRecord, ...]:
        """Return one aggregate's journal records for focused assertions."""
        return tuple(
            [
                event
                async for event in self.database.stream_domain_events(
                    aggregate_type, str(aggregate_id)
                )
            ]
        )
