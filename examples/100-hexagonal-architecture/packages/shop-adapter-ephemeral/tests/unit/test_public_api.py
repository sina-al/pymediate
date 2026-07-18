"""Keep the adapter package's deployment-facing imports intentional."""

import shop.adapters.ephemeral as ephemeral
from shop.adapters.ephemeral.catalogue import EphemeralCatalogue
from shop.adapters.ephemeral.inventory import EphemeralInventory
from shop.adapters.ephemeral.mailer import ConsoleMailer
from shop.adapters.ephemeral.messaging import EphemeralMessageBroker
from shop.adapters.ephemeral.payments import EphemeralPayments
from shop.adapters.ephemeral.sqlite import SqliteDbGateway
from shop.adapters.ephemeral.sqlite_unit_of_work import SqliteUnitOfWork
from shop.adapters.ephemeral.storage import EphemeralStorage


def test_package_exports_are_the_stable_adapter_entry_points() -> None:
    # Arrange
    expected = {
        "ConsoleMailer": ConsoleMailer,
        "EphemeralCatalogue": EphemeralCatalogue,
        "EphemeralInventory": EphemeralInventory,
        "EphemeralMessageBroker": EphemeralMessageBroker,
        "EphemeralPayments": EphemeralPayments,
        "EphemeralStorage": EphemeralStorage,
        "SqliteDbGateway": SqliteDbGateway,
        "SqliteUnitOfWork": SqliteUnitOfWork,
    }

    # Act
    actual = {name: getattr(ephemeral, name) for name in ephemeral.__all__}

    # Assert
    assert actual == expected
    assert set(ephemeral.__all__) == set(expected)
