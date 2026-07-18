"""Stateless secondary adapters shared by every deployment profile."""

from .clock import SystemClock
from .rates import FixedExchangeRates

__all__ = ["FixedExchangeRates", "SystemClock"]
