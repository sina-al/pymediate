"""An HTTP-coupled handler used as a comparison case.

This handler imports FastAPI and raises ``HTTPException`` instead of a domain error.
``tests/test_error_handling.py`` calls it through the CLI mapping and confirms that
the HTTP-specific exception is not converted to an exit code.

Only the comparison test imports this module.
"""

from dataclasses import dataclass

from fastapi import HTTPException
from pymediate.sync import Mediator, Request, RequestHandler, Services

from .core import Catalog, Product, default_catalog


@dataclass
class LeakyGetProduct(Request[Product]):
    """Fetch a product while coupling the request handler to HTTP."""

    product_id: int


class LeakyGetProductHandler(RequestHandler[LeakyGetProduct]):
    """Raise the web framework's exception from a handler."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def __call__(self, request: LeakyGetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            # This chooses an HTTP response inside code also used by non-HTTP callers.
            raise HTTPException(status_code=404, detail="Product not found")
        return product


def build_leaky_mediator() -> Mediator:
    """Build a mediator containing the HTTP-coupled handler."""
    services = Services()
    services.add(LeakyGetProductHandler(default_catalog()))
    return Mediator(services.provider())
