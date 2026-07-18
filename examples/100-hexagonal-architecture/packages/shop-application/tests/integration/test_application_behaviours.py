"""Prove application-level behaviours wrap requests from every business area."""

from unittest.mock import call

from dependency_injector import providers

from shop.application.customers.adjust_store_credit import AdjustStoreCreditRequest
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.ports.logger import Logger

from ..unit.support import autospec
from .support import ApplicationHarness


async def test_logger_behavior_wraps_a_non_order_request(
    application: ApplicationHarness,
) -> None:
    # Arrange
    logger = autospec(Logger)
    await application.mediator.send(OpenCustomerAccountRequest(7))

    # Act
    with application.container.logger.override(providers.Object(logger)):
        response = await application.mediator.send(AdjustStoreCreditRequest(7, 500))

    # Assert
    assert response.store_credit_pence == 500
    assert logger.info.call_args_list[0] == call(
        "request.started",
        request_type="AdjustStoreCreditRequest",
        request_module="shop.application.customers.adjust_store_credit",
    )
    assert logger.info.call_args_list[1].args == ("request.completed",)
    assert logger.info.call_args_list[1].kwargs["response_type"] == "AdjustStoreCreditResponse"
