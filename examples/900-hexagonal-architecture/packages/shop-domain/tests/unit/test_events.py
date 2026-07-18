"""Validate the stable identity carried by domain events."""

import pytest

from shop.domain.events.base import AggregateRef, AggregateType, validate_event_value
from shop.domain.events.customers import CustomerAccountOpenedEvent


@pytest.mark.parametrize("aggregate_id", ["", "   ", 7, None])
def test_aggregate_reference_rejects_an_invalid_identity(aggregate_id: object) -> None:
    # Arrange
    invalid_id = aggregate_id

    # Act
    with pytest.raises(ValueError, match="aggregate id must be non-empty text") as raised:
        AggregateRef(AggregateType.ORDER, invalid_id)  # type: ignore[arg-type]

    # Assert
    assert str(raised.value) == "aggregate id must be non-empty text"


def test_aggregate_reference_requires_a_known_category() -> None:
    # Arrange
    invalid_type = "order"

    # Act
    with pytest.raises(ValueError, match="aggregate type must be a known category") as raised:
        AggregateRef(invalid_type, "7")  # type: ignore[arg-type]

    # Assert
    assert str(raised.value) == "aggregate type must be a known category"


def test_customer_opened_event_owns_stable_identity_and_payload() -> None:
    # Arrange
    event = CustomerAccountOpenedEvent(customer_id=7)

    # Act
    aggregate = event.aggregate
    payload = event.payload()

    # Assert
    assert event.event_name == "customers.account-opened"
    assert event.schema_version == 1
    assert aggregate == AggregateRef(AggregateType.CUSTOMER, "7")
    assert payload == {"customer_id": 7}


def test_nested_json_compatible_event_values_are_accepted() -> None:
    # Arrange
    value = {"totals": [1, 2.5, None], "active": True}

    # Act
    result = validate_event_value(value)

    # Assert
    assert result is None


@pytest.mark.parametrize(
    ("value", "path"),
    [(float("inf"), "payload"), ({"items": [object()]}, "payload.items[0]"), ({1: "x"}, "payload")],
)
def test_non_json_event_values_report_the_exact_path(value: object, path: str) -> None:
    # Arrange
    caught: ValueError | None = None

    # Act
    try:
        validate_event_value(value)
    except ValueError as error:
        caught = error

    # Assert
    assert caught is not None
    assert str(caught) == f"{path} is not JSON-compatible"
