"""Aggregate feature routers without mixing their transport mappings."""

from shop.openapi.routes import WIRING_MODULES, router

__all__ = ["WIRING_MODULES", "router"]
