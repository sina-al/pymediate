"""The domain core: handlers raise plain domain errors and nothing else.

The one rule this example teaches lives here: a handler describes *what went wrong in the
domain* — this product doesn't exist, that item is out of stock — and never how a transport
should report it. No HTTP status, no exit code, no import of FastAPI or argparse. That's
what lets the identical core run behind the web edge (``api.py``) and the CLI (``cli.py``),
each mapping the same error its own way.

This is the synchronous mirror of ``070-error-handling``. The placement rule is identical;
only the API import and the ``async``/``await`` mechanics change.
"""

from dataclasses import dataclass

from pymediate.sync import Mediator, Request, RequestHandler, Services

# ---- Domain errors: plain exceptions, no transport knowledge ----


class ShopError(Exception):
    """Base for every error the shop domain can raise."""


class ProductNotFoundError(ShopError):
    """No product exists with the given id."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")


class OutOfStockError(ShopError):
    """A product exists but can't cover the requested quantity."""

    def __init__(self, product_id: int, requested: int, available: int) -> None:
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"product {product_id} out of stock: requested {requested}, available {available}"
        )


# ---- Value objects ----


@dataclass(frozen=True)
class Product:
    """A product on the shelf."""

    product_id: int
    name: str
    stock: int


@dataclass(frozen=True)
class Order:
    """A placed order."""

    product_id: int
    quantity: int


# ---- Requests ----


@dataclass
class GetProduct(Request[Product]):
    """Fetch a product by id, or raise ``ProductNotFoundError``."""

    product_id: int


@dataclass
class PlaceOrder(Request[Order]):
    """Order a quantity of a product, or raise a domain error."""

    product_id: int
    quantity: int


# ---- A fake catalog and the handlers over it ----


class Catalog:
    """A stand-in for a real product database."""

    def __init__(self, products: dict[int, Product]) -> None:
        self._products = products

    def get(self, product_id: int) -> Product | None:
        """Return the product, or None when it doesn't exist."""
        return self._products.get(product_id)


class GetProductHandler(RequestHandler[GetProduct]):
    """Look up a product. Raises a *domain* error when it's missing — not a 404."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def __call__(self, request: GetProduct) -> Product:
        product = self._catalog.get(request.product_id)
        if product is None:
            raise ProductNotFoundError(request.product_id)
        return product


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Place an order, raising a domain error the edge maps to whatever a transport needs."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    def __call__(self, request: PlaceOrder) -> Order:
        product = self._catalog.get(request.product_id)
        if product is None:
            raise ProductNotFoundError(request.product_id)
        if product.stock < request.quantity:
            raise OutOfStockError(request.product_id, request.quantity, product.stock)
        return Order(product_id=request.product_id, quantity=request.quantity)


def default_catalog() -> Catalog:
    """A small catalog used by both edges and the tests."""
    return Catalog(
        {
            1: Product(product_id=1, name="Widget", stock=5),
            2: Product(product_id=2, name="Gadget", stock=0),
        }
    )


def build_mediator(catalog: Catalog | None = None) -> Mediator:
    """Wire the handlers over a catalog into a mediator. No transport in sight."""
    catalog = catalog if catalog is not None else default_catalog()
    services = Services()
    services.add(GetProductHandler(catalog))
    services.add(PlaceOrderHandler(catalog))
    return Mediator(services.provider())
