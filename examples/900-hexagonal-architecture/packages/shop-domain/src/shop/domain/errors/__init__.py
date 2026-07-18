"""Shared structure for failures expressed in the language of the shop."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar


class DomainError(Exception):
    """Base for expected business failures crossing an application boundary."""

    code: ClassVar[str] = "domain-error"
    title: ClassVar[str] = "Domain rule violated"

    def __init__(self, detail: str, **context: object) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context: Mapping[str, object] = MappingProxyType(context)


class InvalidIdentifierError(DomainError, ValueError):
    """Report an identifier that cannot refer to a domain object."""

    code = "invalid-identifier"
    title = "Invalid identifier"

    def __init__(self, kind: str, value: object) -> None:
        super().__init__(
            f"{kind.replace('_', ' ').capitalize()} must be a positive integer.",
            kind=kind,
            value=value,
        )
