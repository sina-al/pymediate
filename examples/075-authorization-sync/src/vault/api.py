"""Read HTTP credentials, attach a principal, and map access errors to statuses.

The demo parser in ``authn.py`` is unsigned; a production adapter must verify credentials first.
Missing authentication maps to 401. A verified principal that lacks permission maps to 403.
Routes use ``def`` because the mediator is synchronous.
"""

from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .authn import from_http
from .core import (
    AuthenticationRequiredError,
    AuthorizationError,
    Document,
    DocumentNotFoundError,
    DocumentStore,
    EditDocument,
    ListAllDocuments,
    ViewDocument,
    build_mediator,
)


class EditBody(BaseModel):
    """Request body for editing a document."""

    body: str


def create_app(store: DocumentStore | None = None) -> FastAPI:
    """Build a FastAPI app that authenticates at the boundary and authorizes in the core."""
    app = FastAPI(title="Vault")
    mediator = build_mediator(store)

    @app.exception_handler(AuthenticationRequiredError)
    def on_authentication_required(
        request: HTTPRequest, err: AuthenticationRequiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": str(err)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthorizationError)
    def on_denied(request: HTTPRequest, err: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": str(err)})

    @app.exception_handler(DocumentNotFoundError)
    def on_missing(request: HTTPRequest, err: DocumentNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(err)})

    @app.get("/documents/{doc_id}")
    def view(doc_id: int, http_request: HTTPRequest) -> Document:
        principal = from_http(http_request.headers)
        return mediator.send(ViewDocument(doc_id=doc_id, principal=principal))

    @app.get("/documents")
    def list_all(http_request: HTTPRequest) -> list[Document]:
        principal = from_http(http_request.headers)
        return mediator.send(ListAllDocuments(principal=principal))

    @app.put("/documents/{doc_id}")
    def edit(doc_id: int, body: EditBody, http_request: HTTPRequest) -> Document:
        principal = from_http(http_request.headers)
        request = EditDocument(doc_id=doc_id, new_body=body.body, principal=principal)
        return mediator.send(request)

    return app


app = create_app()
