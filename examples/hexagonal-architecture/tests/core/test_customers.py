"""The customers domain, tested the way the article promises: fakes in, assertions out."""

import pytest

from shop_adapter_memory.repositories import MemoryCustomerRepository
from shop_core.customers import (
    GetCustomer,
    GetCustomerHandler,
    RegisterCustomer,
    RegisterCustomerHandler,
)
from shop_core.errors import CustomerNotFoundError


def test_register_customer_stores_and_returns_customer() -> None:
    customers = MemoryCustomerRepository()
    handler = RegisterCustomerHandler(customers)

    customer = handler(RegisterCustomer(name="Ada", email="ada@example.com"))

    assert customer.name == "Ada"
    assert customer.store_credit_cents == 0
    assert customers.get(customer.customer_id) == customer


def test_get_customer_returns_registered_customer() -> None:
    customers = MemoryCustomerRepository()
    registered = RegisterCustomerHandler(customers)(
        RegisterCustomer(name="Ada", email="ada@example.com")
    )

    found = GetCustomerHandler(customers)(GetCustomer(customer_id=registered.customer_id))

    assert found == registered


def test_get_unknown_customer_raises() -> None:
    handler = GetCustomerHandler(MemoryCustomerRepository())

    with pytest.raises(CustomerNotFoundError):
        handler(GetCustomer(customer_id="missing"))
