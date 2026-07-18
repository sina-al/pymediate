"""Convert demo credentials from HTTP or the command line into a principal.

The token format, ``"id;role1,role2;claim1,claim2"``, is unsigned and accepts caller-provided
roles and claims. It is only deterministic input for this example. Production authentication
must verify a signed token, session, or other credential before constructing a trusted
``Principal``.
"""

from collections.abc import Mapping

from .core import Principal


def parse_token(token: str | None) -> Principal | None:
    """Parse the unsigned demo token, or return ``None`` when it is absent."""
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
    """Read the demo bearer token from an HTTP ``Authorization`` header."""
    header = headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return parse_token(header.removeprefix("Bearer "))


def from_cli(token: str | None) -> Principal | None:
    """Read the demo token from a command-line ``--token`` flag."""
    return parse_token(token)
