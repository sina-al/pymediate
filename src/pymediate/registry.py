"""Global registries for request/response type mappings and handler registrations."""

from typing import Any

# Global registry to map request types to their response types
_REQUEST_REGISTRY: dict[type, type] = {}

# Global registry to map request types to their handler classes
_HANDLER_REGISTRY: dict[type, Any] = {}
