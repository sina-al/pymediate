"""Feature routers exposed by the OpenAPI adapter."""

from fastapi import APIRouter

from shop.openapi.routes import customers, invoices, orders, statements

router = APIRouter()
router.include_router(orders.router)
router.include_router(customers.router)
router.include_router(invoices.router)
router.include_router(statements.router)

WIRING_MODULES = (orders, customers, invoices, statements)

__all__ = ["WIRING_MODULES", "router"]
