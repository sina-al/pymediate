"""Verify the observable state of local warehouse and payment substitutes."""

from shop.adapters.ephemeral import EphemeralInventory, EphemeralPayments
from shop.domain.entities.orders import OrderItem


async def test_inventory_records_reservations_and_compensating_releases() -> None:
    # Arrange
    inventory = EphemeralInventory()
    items = (OrderItem("book", 2), OrderItem("mug", 1))

    # Act
    await inventory.reserve(items)
    await inventory.release(items)

    # Assert
    assert inventory.reservations == [items]
    assert inventory.releases == [items]


async def test_payments_record_each_distinct_external_effect() -> None:
    # Arrange
    payments = EphemeralPayments()

    # Act
    await payments.charge(41, 3_900)
    await payments.refund(41, 500)
    await payments.void(42, 1_500)

    # Assert
    assert payments.charges == [(41, 3_900)]
    assert payments.refunds == [(41, 500)]
    assert payments.voids == [(42, 1_500)]
