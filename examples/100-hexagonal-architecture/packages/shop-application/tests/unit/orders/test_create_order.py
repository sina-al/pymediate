"""Test order creation by calling the handler directly."""

from asyncio import CancelledError
from dataclasses import dataclass
from datetime import date
from unittest.mock import MagicMock

import pytest

from shop.application.orders.create_order import CreateOrderHandler, CreateOrderRequest
from shop.domain.entities.orders import Order, OrderItem, OrderLine, Product
from shop.domain.errors import InvalidIdentifierError
from shop.domain.errors.orders import EmptyOrderError, ProductNotFoundError
from shop.domain.events.orders import OrderPlacedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.create_order import (
    CreateOrderClock,
    CreateOrderDbGateway,
    CreateOrderInventory,
    CreateOrderPaymentGateway,
    ProductCatalogue,
)

from ..support import autospec, autospec_unit


@dataclass(frozen=True)
class CreateOrderDependencies:
    """Named mocks used to keep each direct handler test readable."""

    catalogue: MagicMock
    clock: MagicMock
    unit: MagicMock
    database: MagicMock
    inventory: MagicMock
    payments: MagicMock
    journal: MagicMock

    def handle(self) -> CreateOrderHandler:
        """Build the direct handler under test."""
        return CreateOrderHandler(
            self.catalogue,
            self.clock,
            self.unit,
            self.database,
            self.inventory,
            self.payments,
            self.journal,
        )


def dependencies() -> CreateOrderDependencies:
    return CreateOrderDependencies(
        catalogue=autospec(ProductCatalogue),
        clock=autospec(CreateOrderClock),
        unit=autospec_unit(),
        database=autospec(CreateOrderDbGateway),
        inventory=autospec(CreateOrderInventory),
        payments=autospec(CreateOrderPaymentGateway),
        journal=autospec(DomainEventJournal),
    )


async def test_create_order_validates_external_effects_then_commits_messages() -> None:
    # Arrange
    deps = dependencies()
    timeline: list[str] = []
    deps.catalogue.get_product.side_effect = [Product("book", 1_500), Product("mug", 900)]
    deps.clock.today.return_value = date(2026, 7, 13)

    async def next_identity() -> int:
        timeline.append("identity")
        return 42

    async def reserve(items: tuple[OrderItem, ...]) -> None:
        timeline.append("reserve")

    async def charge(order_id: int, amount_pence: int) -> None:
        timeline.append("charge")

    async def enter_transaction() -> MagicMock:
        timeline.append("transaction.enter")
        return deps.unit

    async def insert(order: Order) -> None:
        timeline.append("insert")

    async def exit_transaction(
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        timeline.append("transaction.exit")

    deps.database.next_order_identity.side_effect = next_identity
    deps.inventory.reserve.side_effect = reserve
    deps.payments.charge.side_effect = charge
    deps.unit.__aenter__.side_effect = enter_transaction
    deps.unit.__aexit__.side_effect = exit_transaction
    deps.database.insert_order.side_effect = insert
    handle = deps.handle()
    items = (OrderItem("book", 2), OrderItem("mug", 1))

    # Act
    result = await handle(CreateOrderRequest(7, items))

    # Assert
    assert timeline == [
        "identity",
        "reserve",
        "charge",
        "transaction.enter",
        "insert",
        "transaction.exit",
    ]
    assert result.order_id == 42
    assert result.customer_id == 7
    assert result.total_pence == 3_900
    assert result.status == "placed"
    assert not hasattr(result, "lines")
    assert [call.args for call in deps.catalogue.get_product.await_args_list] == [
        ("book",),
        ("mug",),
    ]
    deps.inventory.reserve.assert_awaited_once_with(items)
    deps.database.insert_order.assert_awaited_once_with(
        Order(
            42,
            7,
            (OrderLine("book", 2, 1_500), OrderLine("mug", 1, 900)),
            3_900,
            date(2026, 7, 13),
        )
    )
    assert deps.database.insert_outbox_message.await_count == 2
    deps.journal.append.assert_awaited_once_with(OrderPlacedEvent(42, 7, 3_900))
    confirmation, invoice = [
        entry.args[0] for entry in deps.database.insert_outbox_message.await_args_list
    ]
    assert confirmation.message.event_type == "shop.orders.order-confirmation-requested"
    assert invoice.message.event_type == "shop.invoices.invoice-requested"
    assert confirmation.message_id != invoice.message_id
    assert confirmation.message.schema_version == invoice.message.schema_version == 1
    assert confirmation.message.payload == {"order_id": 42, "customer_id": 7}
    assert invoice.message.payload == {
        "order_id": 42,
        "customer_id": 7,
        "total_pence": 3_900,
    }
    deps.payments.charge.assert_awaited_once_with(42, 3_900)
    deps.payments.refund.assert_not_awaited()
    deps.inventory.release.assert_not_awaited()
    deps.unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_empty_order_rejects_before_calling_any_dependency() -> None:
    # Arrange
    deps = dependencies()
    handle = deps.handle()

    # Act
    with pytest.raises(EmptyOrderError):
        await handle(CreateOrderRequest(7, ()))

    # Assert
    deps.catalogue.get_product.assert_not_awaited()
    deps.database.next_order_identity.assert_not_awaited()
    deps.inventory.reserve.assert_not_awaited()
    deps.unit.__aenter__.assert_not_awaited()
    deps.payments.charge.assert_not_awaited()


async def test_missing_product_stops_before_identity_or_inventory() -> None:
    # Arrange
    deps = dependencies()
    deps.catalogue.get_product.side_effect = ProductNotFoundError("missing")
    handle = deps.handle()

    # Act
    with pytest.raises(ProductNotFoundError):
        await handle(CreateOrderRequest(7, (OrderItem("missing", 1),)))

    # Assert
    deps.database.next_order_identity.assert_not_awaited()
    deps.inventory.reserve.assert_not_awaited()
    deps.database.insert_order.assert_not_awaited()
    deps.unit.__aenter__.assert_not_awaited()
    deps.payments.charge.assert_not_awaited()


async def test_invalid_customer_stops_before_inventory_or_payment() -> None:
    # Arrange
    deps = dependencies()
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    handle = deps.handle()

    # Act
    with pytest.raises(InvalidIdentifierError):
        await handle(CreateOrderRequest(0, (OrderItem("book", 1),)))

    # Assert
    deps.inventory.reserve.assert_not_awaited()
    deps.payments.charge.assert_not_awaited()
    deps.unit.__aenter__.assert_not_awaited()


@pytest.mark.parametrize("failure", [RuntimeError("payment unavailable"), CancelledError()])
async def test_payment_failure_releases_inventory_without_local_writes(
    failure: BaseException,
) -> None:
    # Arrange
    deps = dependencies()
    items = (OrderItem("book", 1),)
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    deps.payments.charge.side_effect = failure
    handle = deps.handle()

    # Act
    with pytest.raises(type(failure)):
        await handle(CreateOrderRequest(7, items))

    # Assert
    deps.inventory.release.assert_awaited_once_with(items)
    deps.unit.__aenter__.assert_not_awaited()
    deps.database.insert_order.assert_not_awaited()
    deps.journal.append.assert_not_awaited()
    deps.database.insert_outbox_message.assert_not_awaited()
    deps.payments.refund.assert_not_awaited()


@pytest.mark.parametrize("failure", [RuntimeError("write failed"), CancelledError()])
async def test_transaction_failure_refunds_payment_and_releases_inventory(
    failure: BaseException,
) -> None:
    # Arrange
    deps = dependencies()
    items = (OrderItem("book", 1),)
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    deps.database.insert_order.side_effect = failure
    handle = deps.handle()

    # Act
    with pytest.raises(type(failure)):
        await handle(CreateOrderRequest(7, items))

    # Assert
    assert deps.unit.__aexit__.await_args.args[0] is type(failure)
    deps.payments.charge.assert_awaited_once_with(42, 1_500)
    deps.payments.refund.assert_awaited_once_with(42, 1_500)
    deps.inventory.release.assert_awaited_once_with(items)
    deps.journal.append.assert_not_awaited()
    deps.database.insert_outbox_message.assert_not_awaited()


async def test_commit_failure_compensates_after_all_transactional_writes() -> None:
    # Arrange
    deps = dependencies()
    items = (OrderItem("book", 1),)
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    deps.unit.__aexit__.side_effect = RuntimeError("commit failed")
    handle = deps.handle()

    # Act
    with pytest.raises(RuntimeError, match="commit failed"):
        await handle(CreateOrderRequest(7, items))

    # Assert
    deps.database.insert_order.assert_awaited_once()
    deps.journal.append.assert_awaited_once()
    assert deps.database.insert_outbox_message.await_count == 2
    deps.payments.refund.assert_awaited_once_with(42, 1_500)
    deps.inventory.release.assert_awaited_once_with(items)


async def test_charge_and_release_failures_are_reported_together() -> None:
    # Arrange
    deps = dependencies()
    items = (OrderItem("book", 1),)
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    deps.payments.charge.side_effect = RuntimeError("payment unavailable")
    deps.inventory.release.side_effect = RuntimeError("release unavailable")
    handle = deps.handle()

    # Act
    with pytest.raises(ExceptionGroup) as caught:
        await handle(CreateOrderRequest(7, items))

    # Assert
    assert [str(error) for error in caught.value.exceptions] == [
        "payment unavailable",
        "release unavailable",
    ]
    deps.inventory.release.assert_awaited_once_with(items)
    deps.unit.__aenter__.assert_not_awaited()


async def test_transaction_and_all_compensation_failures_are_reported_together() -> None:
    # Arrange
    deps = dependencies()
    items = (OrderItem("book", 1),)
    deps.catalogue.get_product.return_value = Product("book", 1_500)
    deps.clock.today.return_value = date(2026, 7, 13)
    deps.database.next_order_identity.return_value = 42
    deps.database.insert_order.side_effect = RuntimeError("write failed")
    deps.payments.refund.side_effect = RuntimeError("refund unavailable")
    deps.inventory.release.side_effect = RuntimeError("release unavailable")
    handle = deps.handle()

    # Act
    with pytest.raises(ExceptionGroup) as caught:
        await handle(CreateOrderRequest(7, items))

    # Assert
    assert [str(error) for error in caught.value.exceptions] == [
        "write failed",
        "refund unavailable",
        "release unavailable",
    ]
    deps.payments.refund.assert_awaited_once_with(42, 1_500)
    deps.inventory.release.assert_awaited_once_with(items)
