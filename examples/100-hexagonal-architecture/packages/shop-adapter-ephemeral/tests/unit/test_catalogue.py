"""Verify the local product catalogue's small, explicit contract."""

import pytest

from shop.adapters.ephemeral import EphemeralCatalogue
from shop.domain.entities.orders import Product
from shop.domain.errors.orders import ProductNotFoundError


async def test_default_catalogue_exposes_the_demo_products() -> None:
    # Arrange
    catalogue = EphemeralCatalogue()

    # Act
    book = await catalogue.get_product("book")
    mug = await catalogue.get_product("mug")

    # Assert
    assert book == Product("book", 1_500)
    assert mug == Product("mug", 900)


async def test_catalogue_accepts_an_explicit_product_set() -> None:
    # Arrange
    catalogue = EphemeralCatalogue({"pen": Product("pen", 250)})

    # Act
    product = await catalogue.get_product("pen")
    with pytest.raises(ProductNotFoundError) as raised:
        await catalogue.get_product("book")

    # Assert
    assert product == Product("pen", 250)
    assert raised.value.context == {"sku": "book"}
