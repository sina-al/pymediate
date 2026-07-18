"""Exercise runtime validation at the declarative composition boundary."""

import pytest
from dependency_injector import providers
from dependency_injector.errors import Error

from shop.adapters.ephemeral import SqliteDbGateway
from shop.application.orders.container import OrdersContainer, OrdersDbGateway


def test_nominal_adapter_satisfies_runtime_dependency_check() -> None:
    # Arrange
    database = SqliteDbGateway()
    provider = providers.Object(database)

    # Act
    container = OrdersContainer(database=provider)

    # Assert
    assert container.database.instance_of is OrdersDbGateway
    assert container.database() is database


def test_incompatible_adapter_fails_at_composition_boundary() -> None:
    # Arrange
    container = OrdersContainer(database=providers.Object(object()))

    # Act
    with pytest.raises(Error) as error:
        container.database()

    # Assert
    assert "is not an instance of" in str(error.value)
