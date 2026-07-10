"""What the application needs in order to notify people."""

from typing import Protocol


class Mailer(Protocol):
    """Outbound email, reduced to a single send."""

    def send(self, to: str, subject: str, body: str) -> None:
        """Send one email."""
        ...
