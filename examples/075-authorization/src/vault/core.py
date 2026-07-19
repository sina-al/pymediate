"""Authorization policies over a trusted principal carried by each request.

Selective behaviors enforce authentication, role, and multifactor-authentication requirements
before a handler runs. ``EditDocumentHandler`` checks document ownership after loading the
document, keeping the decision beside the resource and avoiding another store lookup.

The boundary adapter is responsible for verifying credentials before it constructs a ``Principal``.
The unsigned parser in ``authn.py`` is demonstration input, not a security boundary.
"""

from dataclasses import dataclass, field, replace
from typing import Any, ClassVar

from pymediate import (
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
    """Caller identity data supplied by a boundary adapter."""

    id: str
    roles: frozenset[str] = frozenset()
    claims: frozenset[str] = frozenset()


class AccessError(Exception):
    """Base class for authentication and authorization denials."""


class AuthorizationError(AccessError):
    """An authenticated principal is not allowed to perform an operation."""


class AuthenticationRequiredError(AccessError):
    """No authenticated principal was supplied for a protected request."""


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


# ---- Marker bases used to select authorization behaviors ----


@dataclass
class AuthenticatedRequest(Request[Any]):
    """Mark a request as requiring an authenticated principal.

    ``principal`` defaults to ``None`` so the adapter can attach it by keyword; the
    ``RequireAuthentication`` behavior rejects the request when it's still ``None``.
    """

    principal: Principal | None = field(default=None, kw_only=True)


@dataclass
class RequiresRole(AuthenticatedRequest):
    """Mark a request as requiring a specific role.

    The role is a class-level fact of the request *type*, so a subclass sets it once.
    """

    required_role: ClassVar[str] = ""


class MutatingCommand:
    """Mark a request as changing state."""


# ---- Requests ----


@dataclass
class ViewDocument(AuthenticatedRequest, Request[Document]):
    """Read a document. Any authenticated principal may attempt it."""

    doc_id: int


@dataclass
class ListAllDocuments(RequiresRole, Request[list[Document]]):
    """List every document after requiring the admin role."""

    required_role: ClassVar[str] = "admin"


@dataclass
class EditDocument(AuthenticatedRequest, MutatingCommand, Request[Document]):
    """Edit a document after authentication, multifactor authentication, and ownership checks."""

    doc_id: int
    new_body: str


# ---- Request-level authorization selected by marker bases ----


class RequireAuthentication(PipelineBehavior[AuthenticatedRequest]):
    """Reject an ``AuthenticatedRequest`` that has no principal.

    Placed outermost in the mediator's behaviors= list, so the role and
    multifactor-authentication behaviors below can assume a principal exists.
    The injected ``audit`` list records every denial — a behavior can take constructor
    dependencies in the same way as a handler.
    """

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    async def __call__(self, request: AuthenticatedRequest, next: Next[Any]) -> Any:
        if request.principal is None:
            self._audit.append(f"deny:unauthenticated {type(request).__name__}")
            raise AuthenticationRequiredError("authentication required")
        return await next()


class RequireRole(PipelineBehavior[RequiresRole]):
    """Reject a ``RequiresRole`` request when the principal lacks its role."""

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    async def __call__(self, request: RequiresRole, next: Next[Any]) -> Any:
        principal = request.principal
        assert principal is not None  # RequireAuthentication ran first (outermost)
        role = type(request).required_role
        if role not in principal.roles:
            self._audit.append(f"deny:role {principal.id} lacks {role!r}")
            raise AuthorizationError(f"requires role {role!r}")
        return await next()


class RequireMfa(PipelineBehavior[AuthenticatedRequest]):
    """Require a multifactor-authentication claim for mutating commands.

    The type parameter is the broad ``AuthenticatedRequest``; ``should_apply`` narrows it to
    mutating commands. The predicate centralizes that selection rule.
    """

    def __init__(self, audit: list[str]) -> None:
        self._audit = audit

    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Apply only to state-changing commands."""
        return isinstance(request, MutatingCommand)

    async def __call__(self, request: AuthenticatedRequest, next: Next[Any]) -> Any:
        principal = request.principal
        assert principal is not None
        if "mfa" not in principal.claims:
            self._audit.append(f"deny:mfa {principal.id}")
            raise AuthorizationError("multifactor authentication required for this action")
        return await next()


# ---- Resource authorization: an injected authorizer used *inside* a handler ----


class DocumentAuthorizer:
    """Decide whether a principal may change a loaded document."""

    def can_edit(self, principal: Principal, document: Document) -> bool:
        """Only the owner (or an admin) may edit a document."""
        return document.owner_id == principal.id or "admin" in principal.roles


# ---- Store and handlers ----


class DocumentStore:
    """Store documents in memory for the example."""

    def __init__(self, documents: dict[int, Document]) -> None:
        self._documents = documents

    def get(self, doc_id: int) -> Document | None:
        return self._documents.get(doc_id)

    def all(self) -> list[Document]:
        return list(self._documents.values())

    def save(self, document: Document) -> None:
        self._documents[document.doc_id] = document


class ViewDocumentHandler(RequestHandler[ViewDocument]):
    """Return a document after the authentication behavior has run."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def __call__(self, request: ViewDocument) -> Document:
        document = self._store.get(request.doc_id)
        if document is None:
            raise DocumentNotFoundError(request.doc_id)
        return document


class ListAllDocumentsHandler(RequestHandler[ListAllDocuments]):
    """List documents. The admin-role check already ran in the pipeline."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    async def __call__(self, request: ListAllDocuments) -> list[Document]:
        return self._store.all()


class EditDocumentHandler(RequestHandler[EditDocument]):
    """Edit a document after checking access to the loaded resource.

    Authentication and multifactor authentication have already passed in the pipeline. This
    handler loads the document once, then passes that instance to the injected authorizer. A
    behavior could load the same document, but that would duplicate or relocate the lookup.
    """

    def __init__(self, store: DocumentStore, authorizer: DocumentAuthorizer) -> None:
        self._store = store
        self._authorizer = authorizer

    async def __call__(self, request: EditDocument) -> Document:
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
    """Return an in-memory store with documents owned by Alice and Bob."""
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
    """Register the three request-level authorization behaviors and handlers."""
    store = store if store is not None else default_store()
    audit = audit if audit is not None else []
    authorizer = DocumentAuthorizer()

    services = Services()
    services.add(RequireAuthentication(audit))
    services.add(RequireRole(audit))
    services.add(RequireMfa(audit))
    services.add(ViewDocumentHandler(store))
    services.add(ListAllDocumentsHandler(store))
    services.add(EditDocumentHandler(store, authorizer))
    return Mediator(
        services.provider(),
        behaviors=[
            RequireAuthentication,  # 1. outermost — every authenticated request
            RequireRole,  # 2. role-gated requests only
            RequireMfa,  # 3. mutating commands only (should_apply)
        ],
    )
