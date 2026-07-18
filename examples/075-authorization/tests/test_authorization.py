"""Tests for the authorization example — the three layers, each visibly separable.

Coarse authorization (authenticated? right role? MFA for a mutation?) is enforced by the
behaviors before the handler. Resource authorization (may this principal edit *this* doc?)
is enforced inside the handler, after the load. The adapters map a denial to their transport.
"""

from collections.abc import AsyncIterator

import httpx2
import pytest
from pymediate import Mediator

from vault.api import create_app
from vault.cli import EXIT_FORBIDDEN, EXIT_OK, main
from vault.core import (
    AuthorizationError,
    EditDocument,
    ListAllDocuments,
    Principal,
    ViewDocument,
    build_mediator,
)

ALICE = Principal(id="alice", roles=frozenset({"user"}), claims=frozenset({"mfa"}))
ALICE_NO_MFA = Principal(id="alice", roles=frozenset({"user"}))
BOB = Principal(id="bob", roles=frozenset({"user"}), claims=frozenset({"mfa"}))
ADMIN = Principal(id="carol", roles=frozenset({"admin"}), claims=frozenset({"mfa"}))


@pytest.fixture
def audit() -> list[str]:
    return []


@pytest.fixture
def mediator(audit: list[str]) -> Mediator:
    return build_mediator(audit=audit)


# ---- Layer 2a: coarse authz — authentication ----


async def test_unauthenticated_is_denied_by_the_behavior(
    mediator: Mediator, audit: list[str]
) -> None:
    with pytest.raises(AuthorizationError, match="authentication required"):
        await mediator.send(ViewDocument(doc_id=1, principal=None))

    assert audit == ["deny:unauthenticated ViewDocument"]  # never reached the handler


async def test_authenticated_view_is_allowed(mediator: Mediator) -> None:
    document = await mediator.send(ViewDocument(doc_id=1, principal=ALICE))
    assert document.owner_id == "alice"


# ---- Layer 2b: coarse authz — role ----


async def test_authentication_is_enforced_before_the_role_check(
    mediator: Mediator, audit: list[str]
) -> None:
    # ListAllDocuments is role-gated *and* authenticated. Unauthenticated, it must be stopped by
    # RequireAuthentication (registered outermost) — never reaching RequireRole, whose
    # `assert principal is not None` trusts exactly that ordering.
    with pytest.raises(AuthorizationError, match="authentication required"):
        await mediator.send(ListAllDocuments(principal=None))

    assert audit == ["deny:unauthenticated ListAllDocuments"]  # the role behavior never ran


async def test_wrong_role_is_denied(mediator: Mediator) -> None:
    with pytest.raises(AuthorizationError, match="requires role 'admin'"):
        await mediator.send(ListAllDocuments(principal=ALICE))  # alice is only a 'user'


async def test_admin_role_is_allowed(mediator: Mediator) -> None:
    documents = await mediator.send(ListAllDocuments(principal=ADMIN))
    assert len(documents) == 2


# ---- Layer 2c: coarse authz — MFA, gated at runtime by should_apply ----


async def test_mutation_without_mfa_is_denied(mediator: Mediator) -> None:
    # should_apply targets mutating commands only, so this MFA check fires on edit...
    with pytest.raises(AuthorizationError, match="MFA required"):
        await mediator.send(EditDocument(doc_id=1, new_body="x", principal=ALICE_NO_MFA))


async def test_read_without_mfa_is_fine(mediator: Mediator) -> None:
    # ...but not on a read: ViewDocument isn't a MutatingCommand, so should_apply skips it.
    document = await mediator.send(ViewDocument(doc_id=1, principal=ALICE_NO_MFA))
    assert document.doc_id == 1


# ---- Layer 3: resource authz — the in-handler ownership check ----


async def test_non_owner_is_denied_in_the_handler(mediator: Mediator) -> None:
    # Bob is authenticated and has MFA, so he clears every behavior — and is still denied,
    # because ownership can only be checked once doc 1 is loaded inside the handler.
    with pytest.raises(AuthorizationError, match="bob may not edit document 1"):
        await mediator.send(EditDocument(doc_id=1, new_body="hacked", principal=BOB))


async def test_owner_can_edit(mediator: Mediator) -> None:
    updated = await mediator.send(EditDocument(doc_id=1, new_body="new", principal=ALICE))
    assert updated.body == "new"


async def test_admin_can_edit_any_document(mediator: Mediator) -> None:
    updated = await mediator.send(EditDocument(doc_id=1, new_body="by admin", principal=ADMIN))
    assert updated.body == "by admin"


# ---- Layer 1: authentication + denial mapping, at two different edges ----


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_http_no_credentials_is_403(client: httpx2.AsyncClient) -> None:
    response = await client.get("/documents/1")  # no Authorization header
    assert response.status_code == 403


async def test_http_authenticated_view_is_200(client: httpx2.AsyncClient) -> None:
    response = await client.get("/documents/1", headers={"Authorization": "Bearer alice;user;mfa"})
    assert response.status_code == 200
    assert response.json()["owner_id"] == "alice"


async def test_http_non_owner_edit_is_403(client: httpx2.AsyncClient) -> None:
    response = await client.put(
        "/documents/1",
        json={"body": "hacked"},
        headers={"Authorization": "Bearer bob;user;mfa"},  # authenticated, but not the owner
    )
    assert response.status_code == 403


def test_cli_no_token_is_forbidden_exit_code() -> None:
    assert main(["view", "1"]) == EXIT_FORBIDDEN  # same denial, different transport


def test_cli_owner_edit_succeeds() -> None:
    assert main(["--token", "alice;user;mfa", "edit", "1", "updated"]) == EXIT_OK
