"""Verify structured request lifecycle logging without running a mediator."""

from unittest.mock import AsyncMock, Mock, call

import pytest

from shop.application.behaviours.logger import LoggerBehavior
from shop.application.orders.create_order import CreateOrderRequest, CreateOrderResponse
from shop.application.services.logger import StructlogLogger
from shop.domain.entities.orders import OrderItem
from shop.ports.logger import Logger

from ..support import autospec


async def test_logger_behavior_records_request_start_and_completion() -> None:
    # Arrange
    logger = autospec(Logger)
    monotonic = Mock(side_effect=[10.0, 10.012345])
    behavior = LoggerBehavior(logger, monotonic)
    request = CreateOrderRequest(7, (OrderItem("book", 1),))
    response = CreateOrderResponse(1, 7, 1_500, 0, "placed")
    proceed = AsyncMock(return_value=response)

    # Act
    result = await behavior(request, proceed)

    # Assert
    assert result is response
    logger.info.assert_has_calls(
        [
            call(
                "request.started",
                request_type="CreateOrderRequest",
                request_module="shop.application.orders.create_order",
            ),
            call(
                "request.completed",
                request_type="CreateOrderRequest",
                request_module="shop.application.orders.create_order",
                duration_ms=12.345,
                response_type="CreateOrderResponse",
            ),
        ]
    )
    logger.error.assert_not_called()


async def test_logger_behavior_records_request_failure_and_reraises() -> None:
    # Arrange
    logger = autospec(Logger)
    monotonic = Mock(side_effect=[20.0, 20.004])
    behavior = LoggerBehavior(logger, monotonic)
    request = CreateOrderRequest(7, (OrderItem("book", 1),))
    proceed = AsyncMock(side_effect=RuntimeError("payment unavailable"))

    # Act
    with pytest.raises(RuntimeError, match="payment unavailable"):
        await behavior(request, proceed)

    # Assert
    logger.error.assert_called_once_with(
        "request.failed",
        request_type="CreateOrderRequest",
        request_module="shop.application.orders.create_order",
        duration_ms=4.0,
        error_type="RuntimeError",
    )


def test_structlog_service_delegates_structured_events() -> None:
    # Arrange
    backend = autospec(Logger)
    service = StructlogLogger(backend)

    # Act
    service.info("request.started", request_type="CreateOrderRequest")
    service.error("request.failed", error_type="RuntimeError")

    # Assert
    backend.info.assert_called_once_with("request.started", request_type="CreateOrderRequest")
    backend.error.assert_called_once_with("request.failed", error_type="RuntimeError")
