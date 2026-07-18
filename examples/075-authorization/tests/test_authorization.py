"""Tests for authentication requirements and request/resource authorization."""

from collections.abc import AsyncIterator

import httpx2
import pytest
from pymediate import Mediator

from vault.api import create_app
from vault.cli import EXIT_ACCESS_DENIED, EXIT_OK, main
from vault.core import (
    AuthenticationRequiredError,
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


# ---- Request-level authentication requirement ----


async def test_unauthenticated_is_denied_by_the_behavior(
    mediator: Mediator, audit: list[str]
) -> None:
    with pytest.raises(AuthenticationRequiredError, match="authentication required"):
        await mediator.send(ViewDocument(doc_id=1, principal=None))

    assert audit == ["deny:unauthenticated ViewDocument"]  # never reached the handler


async def test_authenticated_view_is_allowed(mediator: Mediator) -> None:
    document = await mediator.send(ViewDocument(doc_id=1, principal=ALICE))
    assert document.owner_id == "alice"


# ---- Request-level role requirement ----


async def test_authentication_is_enforced_before_the_role_check(
    mediator: Mediator, audit: list[str]
) -> None:
    # ListAllDocuments is role-gated *and* authenticated. Unauthenticated, it must be stopped by
    # RequireAuthentication (registered outermost) — never reaching RequireRole, whose
    # `assert principal is not None` trusts exactly that ordering.
    with pytest.raises(AuthenticationRequiredError, match="authentication required"):
        await mediator.send(ListAllDocuments(principal=None))

    assert audit == ["deny:unauthenticated ListAllDocuments"]  # the role behavior never ran


async def test_wrong_role_is_denied(mediator: Mediator) -> None:
    with pytest.raises(AuthorizationError, match="requires role 'admin'"):
        await mediator.send(ListAllDocuments(principal=ALICE))  # alice is only a 'user'


async def test_admin_role_is_allowed(mediator: Mediator) -> None:
    documents = await mediator.send(ListAllDocuments(principal=ADMIN))
    assert len(documents) == 2


# ---- Multifactor authentication for state-changing requests ----


async def test_mutation_without_mfa_is_denied(mediator: Mediator) -> None:
    # should_apply targets mutating commands, so this multifactor check runs on edit.
    with pytest.raises(AuthorizationError, match="multifactor authentication required"):
        await mediator.send(EditDocument(doc_id=1, new_body="x", principal=ALICE_NO_MFA))


async def test_read_without_mfa_is_allowed(mediator: Mediator) -> None:
    # ViewDocument is not a MutatingCommand, so should_apply skips the check.
    document = await mediator.send(ViewDocument(doc_id=1, principal=ALICE_NO_MFA))
    assert document.doc_id == 1


# ---- Resource authorization after loading the document ----


async def test_non_owner_is_denied_in_the_handler(mediator: Mediator) -> None:
    # Bob passes the request-level checks but does not own the loaded document.
    with pytest.raises(AuthorizationError, match="bob may not edit document 1"):
        await mediator.send(EditDocument(doc_id=1, new_body="hacked", principal=BOB))


async def test_owner_can_edit(mediator: Mediator) -> None:
    updated = await mediator.send(EditDocument(doc_id=1, new_body="new", principal=ALICE))
    assert updated.body == "new"


async def test_admin_can_edit_any_document(mediator: Mediator) -> None:
    updated = await mediator.send(EditDocument(doc_id=1, new_body="by admin", principal=ADMIN))
    assert updated.body == "by admin"


# ---- HTTP and CLI status mappings ----


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_http_no_credentials_is_401(client: httpx2.AsyncClient) -> None:
    response = await client.get("/documents/1")  # no Authorization header
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


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


def test_cli_no_token_uses_access_denied_exit_code() -> None:
    assert main(["view", "1"]) == EXIT_ACCESS_DENIED


def test_cli_owner_edit_succeeds() -> None:
    assert main(["--token", "alice;user;mfa", "edit", "1", "updated"]) == EXIT_OK
