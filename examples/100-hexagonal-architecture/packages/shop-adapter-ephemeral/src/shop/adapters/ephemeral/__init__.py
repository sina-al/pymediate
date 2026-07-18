"""Zero-setup implementations for local Shop dependencies."""

from .catalogue import EphemeralCatalogue
from .inventory import EphemeralInventory
from .mailer import ConsoleMailer
from .messaging import EphemeralMessageBroker
from .payments import EphemeralPayments
from .sqlite import SqliteDbGateway
from .sqlite_unit_of_work import SqliteUnitOfWork
from .storage import EphemeralStorage

__all__ = [
    "ConsoleMailer",
    "EphemeralCatalogue",
    "EphemeralInventory",
    "EphemeralMessageBroker",
    "EphemeralPayments",
    "EphemeralStorage",
    "SqliteDbGateway",
    "SqliteUnitOfWork",
]
