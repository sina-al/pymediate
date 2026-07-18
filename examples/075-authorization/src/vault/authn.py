"""Authentication: the *only* transport-specific auth code, isolated to one file.

Parsing a credential into a ``Principal`` is where the transport shows through — an HTTP
header here, a CLI flag there. Everything downstream (the behaviors, the handler) sees only a
``Principal`` and never learns where it came from. That's the third layer: authentication is
an adapter concern.

The token format is deliberately fake — ``"id;role1,role2;claim1,claim2"`` — because this
example is about *placement*, not crypto. A real adapter would verify a signed JWT or a
session cookie and build the same ``Principal``.
"""

from collections.abc import Mapping

from .core import Principal


def parse_token(token: str | None) -> Principal | None:
    """Turn a fake ``id;roles;claims`` token into a ``Principal``, or ``None`` if absent."""
    if not token:
        return None
    parts = token.split(";")
    principal_id = parts[0].strip()
    if not principal_id:
        return None
    roles = frozenset(r for r in parts[1].split(",") if r) if len(parts) > 1 else frozenset()
    claims = frozenset(c for c in parts[2].split(",") if c) if len(parts) > 2 else frozenset()
    return Principal(id=principal_id, roles=roles, claims=claims)


def from_http(headers: Mapping[str, str]) -> Principal | None:
    """HTTP adapter: read a ``Bearer`` token from the ``Authorization`` header."""
    header = headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return parse_token(header.removeprefix("Bearer "))


def from_cli(token: str | None) -> Principal | None:
    """CLI adapter: read the token straight from a ``--token`` flag."""
    return parse_token(token)
