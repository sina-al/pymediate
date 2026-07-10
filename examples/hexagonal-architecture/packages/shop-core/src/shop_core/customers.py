"""The customers domain: registering and reading customers."""

from dataclasses import dataclass
from uuid import uuid4

from pymediate import Handler, Request

from shop_domain.customers import Customer
from shop_ports.customers import CustomerRepository

from .errors import CustomerNotFoundError


@dataclass
class RegisterCustomer(Request[Customer]):
    """Register a customer; responds with the created Customer."""

    name: str
    email: str


class RegisterCustomerHandler(Handler[RegisterCustomer]):
    """Creates customers in the repository."""

    def __init__(self, customers: CustomerRepository) -> None:
        self._customers = customers

    def __call__(self, request: RegisterCustomer) -> Customer:
        customer = Customer(customer_id=uuid4().hex, name=request.name, email=request.email)
        self._customers.add(customer)
        return customer


@dataclass
class GetCustomer(Request[Customer]):
    """Fetch a customer by id; responds with the Customer."""

    customer_id: str


class GetCustomerHandler(Handler[GetCustomer]):
    """Looks up existing customers."""

    def __init__(self, customers: CustomerRepository) -> None:
        self._customers = customers

    def __call__(self, request: GetCustomer) -> Customer:
        customer = self._customers.get(request.customer_id)
        if customer is None:
            raise CustomerNotFoundError(request.customer_id)
        return customer
