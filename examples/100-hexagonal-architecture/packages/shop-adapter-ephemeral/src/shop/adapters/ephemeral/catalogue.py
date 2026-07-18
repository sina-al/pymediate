"""Process-local product catalogue for profiles without a catalogue service."""

from collections.abc import Mapping

from shop.domain.entities.orders import Product
from shop.domain.errors.orders import ProductNotFoundError
from shop.ports.orders.create_order import ProductCatalogue


class EphemeralCatalogue(ProductCatalogue):
    """Serve a small immutable product set without assigning a cloud provider."""

    def __init__(self, products: Mapping[str, Product] | None = None) -> None:
        selected = (
            {"book": Product("book", 1_500), "mug": Product("mug", 900)}
            if products is None
            else products
        )
        self._products = dict(selected)

    async def get_product(self, sku: str) -> Product:
        """Return one product or the application's structured missing-product error."""
        try:
            return self._products[sku]
        except KeyError:
            raise ProductNotFoundError(sku) from None
