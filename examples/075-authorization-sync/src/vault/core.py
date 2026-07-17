"""The core: identity travels in the request, and authorization lives in two of the three layers.

The revelation this example teaches: **authentication is a transport concern, authorization is
a domain concern — and the entity-dependent slice of authorization belongs in the handler, not
the pipeline.** This module holds the two authorization layers that are domain code:

- **Coarse authorization** — "is this principal allowed to *attempt* this at all?" (logged in?
  right role? MFA for a mutation?) — is a set of **selective pipeline behaviors**, keyed by
  marker base classes. This is the ``[Authorize]`` / ``[Authorize(Roles=…)]`` analog.
- **Resource authorization** — "may this principal edit *this specific document*?" — is an
  **imperative check inside the handler**, run *after* the entity loads. A pre-dispatch
  behavior can't do it: the document isn't loaded yet when a behavior runs.

Identity rides in the request as a ``principal`` field; there is no ambient ``HttpContext``.
The adapter (``authn.py`` + ``api.py`` / ``cli.py``) parses a credential and attaches it — that
is the *only* transport-specific auth code, and it's the third layer.

This is the synchronous mirror of ``075-authorization``. The placement rule is identical; only
the API import and the absence of ``async``/``await`` change.
"""

from dataclasses import dataclass, field, replace
from typing import Any, ClassVar

from pymediate.sync import (
    Mediator,
    Next,
    PipelineBehavior,
    Request,
    RequestHandler,
    Services,
)

# ---- Identity and denial ----


@dataclass(frozen=True)
class Principal:
    """An authenticated caller. Built by the adapter from a credential, carried in the request."""

    id: str
    roles: frozenset[str] = frozenset()
    claims: frozenset[str] = frozenset()


class AuthorizationError(Exception):
    """A domain denial. The adapter maps it to a transport (HTTP 403, a CLI exit code)."""


class DocumentNotFoundError(Exception):
    """No document exists with the given id."""

    def __init__(self, doc_id: int) -> None:
        self.doc_id = doc_id
        super().__init__(f"document not found: {doc_id}")


# ---- Value objects ----


@dataclass(frozen=True)
class Document:
    """A stored document with an owner."""

    doc_id: int
    owner_id: str
    body: str


# ---- Marker bases: wearing one is like wearing an [Authorize] attribute ----


@dataclass
class AuthenticatedRequest(Request[Any]):
    """Marker: this request requires a logged-in principal. The ``[Authorize]`` analog.

    ``principal`` defaults to ``None`` so the adapter can attach it by keyword; the
    ``RequireAuthentication`` behavior rejects the request when it's still ``None``.
    """

    principal: Principal | None = field(default=None, kw_only=True)


@dataclass
class RequiresRole(AuthenticatedRequest):
    """Marker: requires a specific role. The ``[Authorize(Roles=…)]`` analog.

    The role is a class-level fact of the request *type*, so a subclass sets it once.
    """

    required_role: ClassVar[str] = ""


class MutatingCommand:
    """Marker mixin: a request that changes state. ``RequireMfa`` gates these at runtime."""


# ---- Requests ----


@dataclass
class ViewDocument(AuthenticatedRequest, Request[Document]):
    """Read a document. Any authenticated principal may attempt it."""

    doc_id: int


@dataclass
class ListAllDocuments(RequiresRole, Request[list[Document]]):
    """List every document. Admins only — coarse authorization by role."""

    required_role: ClassVar[str] = "admin"


@dataclass
class EditDocument(AuthenticatedRequest, MutatingCommand, Request[Document]):
    """Edit a document's body. Authenticated + MFA to attempt; owner (or admin) to succeed."""

    doc_id: int
    new_body: str


# ---- Coarse authorization: selective behaviors keyed by the marker bases ----


class RequireAuthentication(PipelineBehavior[AuthenticatedRequest]):
    """Reject any ``AuthenticatedRequest`` with no principal. The ``RequireAuthorization`` analog.

    Registered outermost, so the role and MFA behaviors below can assume a principal exists.
    The injected ``audit`` list records every denial — a behavior can take constructor
    dependencies just like a handler.
    """

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    def __call__(self, request: AuthenticatedRequest, next: Next[Any]) -> Any:
        if request.principal is None:
            self._audit.append(f"deny:unauthenticated {type(request).__name__}")
            raise AuthorizationError("authentication required")
        return next()


class RequireRole(PipelineBehavior[RequiresRole]):
    """Reject a ``RequiresRole`` request lacking the role. The ``[Authorize(Roles=…)]`` analog."""

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    def __call__(self, request: RequiresRole, next: Next[Any]) -> Any:
        principal = request.principal
        assert principal is not None  # RequireAuthentication ran first (outermost)
        role = type(request).required_role
        if role not in principal.roles:
            self._audit.append(f"deny:role {principal.id} lacks {role!r}")
            raise AuthorizationError(f"requires role {role!r}")
        return next()


class RequireMfa(PipelineBehavior[AuthenticatedRequest]):
    """Require an ``mfa`` claim — but only for mutating commands, decided at runtime.

    The type parameter is the broad ``AuthenticatedRequest``; ``should_apply`` narrows it to
    just the mutating commands. That runtime gate is something a static ``[Authorize]``
    attribute can't express — a read and a write of the same base type are treated differently.
    """

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Apply only to state-changing commands."""
        return isinstance(request, MutatingCommand)

    def __call__(self, request: AuthenticatedRequest, next: Next[Any]) -> Any:
        principal = request.principal
        assert principal is not None
        if "mfa" not in principal.claims:
            self._audit.append(f"deny:mfa {principal.id}")
            raise AuthorizationError("MFA required for this action")
        return next()


# ---- Resource authorization: an injected authorizer used *inside* a handler ----


class DocumentAuthorizer:
    """The ``IAuthorizationService`` analog: decides access to a *loaded* resource."""

    def can_edit(self, principal: Principal, document: Document) -> bool:
        """Only the owner (or an admin) may edit a document."""
        return document.owner_id == principal.id or "admin" in principal.roles


# ---- Store and handlers ----


class DocumentStore:
    """A stand-in for a real document database."""

    def __init__(self, documents: dict[int, Document]) -> None:
        self._documents = documents

    def get(self, doc_id: int) -> Document | None:
        return self._documents.get(doc_id)

    def all(self) -> list[Document]:
        return list(self._documents.values())

    def save(self, document: Document) -> None:
        self._documents[document.doc_id] = document


class ViewDocumentHandler(RequestHandler[ViewDocument]):
    """Return a document. Coarse authz (authenticated) already passed in the pipeline."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    def __call__(self, request: ViewDocument) -> Document:
        document = self._store.get(request.doc_id)
        if document is None:
            raise DocumentNotFoundError(request.doc_id)
        return document


class ListAllDocumentsHandler(RequestHandler[ListAllDocuments]):
    """List documents. The admin-role check already ran in the pipeline."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    def __call__(self, request: ListAllDocuments) -> list[Document]:
        return self._store.all()


class EditDocumentHandler(RequestHandler[EditDocument]):
    """Edit a document — with the resource-authorization check that *must* live here.

    Authentication and MFA already passed in the pipeline. Ownership is different: it depends
    on the document, which doesn't exist until this handler loads it. So the check is
    imperative, right after the load, using the injected authorizer — the one authorization
    that a pre-dispatch behavior structurally cannot perform.
    """

    def __init__(self, store: DocumentStore, authorizer: DocumentAuthorizer) -> None:
        self._store = store
        self._authorizer = authorizer

    def __call__(self, request: EditDocument) -> Document:
        document = self._store.get(request.doc_id)
        if document is None:
            raise DocumentNotFoundError(request.doc_id)
        principal = request.principal
        assert principal is not None  # guaranteed by RequireAuthentication
        if not self._authorizer.can_edit(principal, document):
            raise AuthorizationError(f"{principal.id} may not edit document {document.doc_id}")
        updated = replace(document, body=request.new_body)
        self._store.save(updated)
        return updated


def default_store() -> DocumentStore:
    """A small store: doc 1 owned by alice, doc 2 owned by bob."""
    return DocumentStore(
        {
            1: Document(doc_id=1, owner_id="alice", body="alice's notes"),
            2: Document(doc_id=2, owner_id="bob", body="bob's notes"),
        }
    )


def build_mediator(
    store: DocumentStore | None = None,
    audit: list[str] | None = None,
) -> Mediator:
    """Wire the three coarse-authz behaviors and the handlers into a mediator."""
    store = store if store is not None else default_store()
    audit = audit if audit is not None else []
    authorizer = DocumentAuthorizer()

    services = Services()
    services.add(RequireAuthentication(audit))  # 1. outermost — every authenticated request
    services.add(RequireRole(audit))  # 2. role-gated requests only
    services.add(RequireMfa(audit))  # 3. mutating commands only (should_apply)
    services.add(ViewDocumentHandler(store))
    services.add(ListAllDocumentsHandler(store))
    services.add(EditDocumentHandler(store, authorizer))
    return Mediator(services.provider())
