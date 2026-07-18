"""Test customer invariants without application or persistence machinery."""

from dataclasses import FrozenInstanceError

import pytest

from shop.domain.entities.customers import CustomerAccount
from shop.domain.errors import InvalidIdentifierError
from shop.domain.errors.customers import InvalidStoreCreditBalanceError, InvalidStoreCreditError


def test_open_customer_account_has_an_immutable_zero_balance() -> None:
    # Arrange
    customer_id = 7

    # Act
    account = CustomerAccount.open(customer_id)

    # Assert
    assert account == CustomerAccount(customer_id=7, store_credit_pence=0)


def test_store_credit_accumulates_without_mutating_the_original_account() -> None:
    # Arrange
    account = CustomerAccount(7, 500)

    # Act
    credited = account.add_store_credit(250)

    # Assert
    assert account.store_credit_pence == 500
    assert credited.store_credit_pence == 750


@pytest.mark.parametrize("customer_id", [0, -1, True])
def test_customer_identity_must_be_a_positive_integer(customer_id: int) -> None:
    # Arrange
    caught: InvalidIdentifierError | None = None

    # Act
    try:
        CustomerAccount.open(customer_id)
    except InvalidIdentifierError as error:
        caught = error

    # Assert
    assert caught is not None
    assert caught.context == {"kind": "customer_id", "value": customer_id}


@pytest.mark.parametrize("balance_pence", [-1, True])
def test_stored_credit_balance_cannot_be_negative_or_boolean(balance_pence: int) -> None:
    # Arrange
    caught: InvalidStoreCreditBalanceError | None = None

    # Act
    try:
        CustomerAccount(7, balance_pence)
    except InvalidStoreCreditBalanceError as error:
        caught = error

    # Assert
    assert caught is not None
    assert caught.context == {"balance_pence": balance_pence}


@pytest.mark.parametrize("amount_pence", [0, -1, True])
def test_store_credit_adjustment_must_be_positive(amount_pence: int) -> None:
    # Arrange
    account = CustomerAccount(7)
    caught: InvalidStoreCreditError | None = None

    # Act
    try:
        account.add_store_credit(amount_pence)
    except InvalidStoreCreditError as error:
        caught = error

    # Assert
    assert caught is not None
    assert caught.context == {"amount_pence": amount_pence}


def test_customer_entity_is_immutable() -> None:
    # Arrange
    account = CustomerAccount(7)
    caught: FrozenInstanceError | None = None

    # Act
    try:
        account.store_credit_pence = 100  # type: ignore[misc]
    except FrozenInstanceError as error:
        caught = error

    # Assert
    assert caught is not None
