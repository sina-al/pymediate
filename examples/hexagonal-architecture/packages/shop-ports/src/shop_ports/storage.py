"""What the application needs from file storage."""

from typing import Protocol


class FileStorage(Protocol):
    """Somewhere to put generated files (exports), returning a fetchable location."""

    def write(self, name: str, content: bytes) -> str:
        """Store the content under the given name and return its URL."""
        ...
