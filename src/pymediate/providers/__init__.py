"""Service provider implementations for PyMediate.

This module contains implementations of the ServiceProvider protocol for
integrating with various dependency injection frameworks and containers.
"""

from .dependency_injector import DependencyInjectorServiceProvider

__all__ = ["DependencyInjectorServiceProvider"]
