"""Nested complex types - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, Services


@dataclass
class Address:
    street: str
    city: str
    zip_code: str


@dataclass
class Order:
    order_id: int
    total: float


@dataclass
class CustomerDetailsResponse:
    customer_id: int
    name: str
    addresses: list[Address]
    orders: list[Order]
    metadata: dict[str, str]


@dataclass
class GetCustomerDetailsRequest(Request[CustomerDetailsResponse]):
    customer_id: int


class GetCustomerDetailsHandler(Handler[GetCustomerDetailsRequest]):
    def __call__(self, request: GetCustomerDetailsRequest) -> CustomerDetailsResponse:
        return CustomerDetailsResponse(
            customer_id=request.customer_id,
            name="Alice",
            addresses=[Address(street="123 Main St", city="Springfield", zip_code="12345")],
            orders=[Order(order_id=1, total=99.99), Order(order_id=2, total=149.99)],
            metadata={"tier": "premium", "region": "us-west"},
        )


# Usage
services = Services()
services.add(GetCustomerDetailsHandler())
provider = services.provider()
mediator = Mediator(provider)

request = GetCustomerDetailsRequest(customer_id=1)
response = mediator.send(request)

# Type-safe nested access
customer_id: int = response.customer_id
addresses: list[Address] = response.addresses
first_address: Address = addresses[0]
city: str = first_address.city

orders: list[Order] = response.orders
first_order: Order = orders[0]
total: float = first_order.total

metadata: dict[str, str] = response.metadata
tier: str = metadata["tier"]
