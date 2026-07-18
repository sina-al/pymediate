"""Show scoped Dependency Injector overrides without replacing the application."""

from dataclasses import dataclass, field
from datetime import date
from typing import cast

from dependency_injector import providers

from shop.adapters.ephemeral import SqliteDbGateway
from shop.application.orders.create_order import CreateOrderRequest
from shop.bindings.loading import create_application_container, load_wiring
from shop.domain.entities.orders import OrderItem
from shop.ports.orders.cancel_order import (
    CancelOrderInventory,
    CancelOrderMailer,
    CancelOrderPaymentGateway,
)
from shop.ports.orders.create_order import (
    CreateOrderClock,
    CreateOrderInventory,
    CreateOrderPaymentGateway,
)
from shop.ports.orders.export_orders import ExportOrdersMailer
from shop.ports.orders.refund_order import RefundOrderMailer, RefundOrderPaymentGateway
from shop.ports.orders.send_order_confirmation import SendOrderConfirmationMailer


@dataclass(frozen=True)
class FixedClock(CreateOrderClock):
    value: date

    def today(self) -> date:
        return self.value


@dataclass
class RecordingInventory(CreateOrderInventory, CancelOrderInventory):
    reserved: list[tuple[OrderItem, ...]] = field(default_factory=list)

    async def reserve(self, items: tuple[OrderItem, ...]) -> None:
        self.reserved.append(items)

    async def release(self, items: tuple[OrderItem, ...]) -> None:
        pass


@dataclass
class RecordingPayments(
    CreateOrderPaymentGateway,
    CancelOrderPaymentGateway,
    RefundOrderPaymentGateway,
):
    charges: list[tuple[int, int]] = field(default_factory=list)

    async def charge(self, order_id: int, amount_pence: int) -> None:
        self.charges.append((order_id, amount_pence))

    async def refund(self, order_id: int, amount_pence: int) -> None:
        pass

    async def void(self, order_id: int, amount_pence: int) -> None:
        pass


@dataclass
class RecordingMailer(
    SendOrderConfirmationMailer,
    CancelOrderMailer,
    RefundOrderMailer,
    ExportOrdersMailer,
):
    messages: list[tuple[str, str]] = field(default_factory=list)

    async def send(self, recipient: str, subject: str, idempotency_key: str | None = None) -> None:
        self.messages.append((recipient, subject))

    async def send_export_ready(
        self,
        recipient: str,
        download_url: str,
        idempotency_key: str | None = None,
    ) -> None:
        self.messages.append((recipient, download_url))


async def test_selected_outward_ports_can_be_overridden_for_one_mediator_scenario() -> None:
    # Arrange
    wiring = load_wiring()
    async with wiring.activate("application"):
        container = create_application_container(wiring)
        database = cast("SqliteDbGateway", container.database())
        inventory = RecordingInventory()
        payments = RecordingPayments()
        mailer = RecordingMailer()
        placed_on = date(2026, 7, 13)
        items = (OrderItem("book", 2),)

        # Act
        with (
            container.clock.override(providers.Object(FixedClock(placed_on))),
            container.inventory.override(providers.Object(inventory)),
            container.payments.override(providers.Object(payments)),
            container.mailer.override(providers.Object(mailer)),
        ):
            result = await container.mediator().send(CreateOrderRequest(7, items))

        # Assert
        assert result.order_id == 1
        assert (await database.get_order(result.order_id)).placed_on == placed_on
        assert not hasattr(result, "placed_on")
        assert not hasattr(result, "lines")
        assert inventory.reserved == [items]
        assert payments.charges == [(1, 3_000)]
        assert mailer.messages == []
