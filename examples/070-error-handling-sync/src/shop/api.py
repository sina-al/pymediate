"""HTTP edge: map each domain error to a status code, once, centrally.

The routes describe only the happy path. Failure is handled by the exception handlers
registered below — the FastAPI construct for turning an exception into a response. The core
raised a ``ProductNotFoundError``; *this* layer decides that means 404. A different edge
decides something else (see ``cli.py``). Endpoints are plain ``def`` because the core is
synchronous.
"""

from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse

from .core import (
    Catalog,
    GetProduct,
    Order,
    OutOfStockError,
    PlaceOrder,
    Product,
    ProductNotFoundError,
    build_mediator,
)


def create_app(catalog: Catalog | None = None) -> FastAPI:
    """Build a FastAPI app over the shop core, mapping domain errors to HTTP statuses."""
    app = FastAPI(title="Shop")
    mediator = build_mediator(catalog)

    @app.exception_handler(ProductNotFoundError)
    def on_not_found(request: HTTPRequest, err: ProductNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(err)})

    @app.exception_handler(OutOfStockError)
    def on_out_of_stock(request: HTTPRequest, err: OutOfStockError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": str(err)})

    @app.get("/products/{product_id}")
    def get_product(product_id: int) -> Product:
        return mediator.send(GetProduct(product_id=product_id))

    @app.post("/products/{product_id}/orders", status_code=201)
    def place_order(product_id: int, quantity: int) -> Order:
        return mediator.send(PlaceOrder(product_id=product_id, quantity=quantity))

    return app


app = create_app()
