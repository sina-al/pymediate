"""Parameterizing EventHandler with a non-Event type - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate import EventHandler


@dataclass
class NotAnEvent:
    order_id: int


# ERROR: EventHandler's type parameter is bound to Event
class SendConfirmation(EventHandler[NotAnEvent]):
    @override
    def __call__(self, event: NotAnEvent) -> None:
        pass
