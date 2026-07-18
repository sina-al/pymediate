"""HTTP edge: authenticate from the header, attach the principal, map denials to statuses.

Each route does the same two-step: parse the credential into a ``Principal`` (``authn.py``),
then build the request with that principal attached. The authorization that follows is the
core's job, identical to every other transport. A denial comes back as ``AuthorizationError``,
which this layer maps to 403. Routes are plain ``def`` because the core is synchronous.
"""

from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .authn import from_http
from .core import (
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
    """Build a FastAPI app that authenticates at the edge and authorizes in the core."""
    app = FastAPI(title="Vault")
    mediator = build_mediator(store)

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
