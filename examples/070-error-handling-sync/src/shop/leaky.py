"""The anti-pattern, isolated so you can watch it break a non-HTTP caller.

Look at the import list: a *core* handler now depends on FastAPI. That's the smell. This
handler raises ``HTTPException`` instead of a domain error — convenient behind a web server,
ruinous anywhere else. ``tests/test_error_handling.py`` drives it through the CLI's
domain-error mapping and shows the ``HTTPException`` sail straight past ``except
ProductNotFoundError`` — a batch job crashing with an HTTP error and no client to send it to.

Nothing imports this module except the test. It exists to fail on purpose.
"""

from dataclasses import dataclass

from fastapi import HTTPException  # ← a core handler should never need this
from pymediate.sync import Mediator, Request, RequestHandler, Services

from .core import Catalog, Product, default_catalog


@dataclass
class LeakyGetProduct(Request[Product]):
    """Same intent as ``core.GetProduct`` — written the wrong way."""

    product_id: int


class LeakyGetProductHandler(RequestHandler[LeakyGetProduct]):
    """Raises the web framework's own exception from inside the domain. Don't do this."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def __call__(self, request: LeakyGetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            # The leak: an HTTP status, decided inside the core, for a caller that may not
            # even speak HTTP.
            raise HTTPException(status_code=404, detail="Product not found")
        return product


def build_leaky_mediator() -> Mediator:
    """Wire the leaky handler so a test can drive it through the CLI mapping."""
    services = Services()
    services.add(LeakyGetProductHandler(default_catalog()))
    return Mediator(services.provider())
