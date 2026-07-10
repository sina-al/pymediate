"""The repository contract: what every persistence adapter must honor.

One suite, parametrized over implementations. If an adapter passes these, the core
works on it — dicts, Postgres, and Neo4j prove it by running the identical assertions.
"""

from shop_domain.customers import Customer
from shop_domain.orders import LineItem, Order, OrderStatus
from shop_ports.customers import CustomerRepository
from shop_ports.orders import OrderRepository

Repos = tuple[OrderRepository, CustomerRepository]

ADA = Customer(customer_id="ada", name="Ada", email="ada@example.com")


def _order(order_id: str, customer_id: str = "ada") -> Order:
    return Order(
        order_id=order_id,
        customer_id=customer_id,
        items=[
            LineItem(sku="widget", quantity=2, unit_price_cents=1999),
            LineItem(sku="gadget", quantity=1, unit_price_cents=500),
        ],
    )


def test_customer_roundtrip(repos: Repos) -> None:
    _, customers = repos
    customers.add(ADA)

    assert customers.get("ada") == ADA


def test_unknown_customer_is_none(repos: Repos) -> None:
    _, customers = repos

    assert customers.get("ghost") is None


def test_credit_accumulates(repos: Repos) -> None:
    _, customers = repos
    customers.add(ADA)

    customers.credit("ada", 500)
    updated = customers.credit("ada", 250)

    assert updated is not None
    assert updated.store_credit_cents == 750
    assert customers.get("ada").store_credit_cents == 750  # type: ignore[union-attr]


def test_credit_unknown_customer_is_none(repos: Repos) -> None:
    _, customers = repos

    assert customers.credit("ghost", 500) is None


def test_order_roundtrip_preserves_items_and_status(repos: Repos) -> None:
    orders, customers = repos
    customers.add(ADA)
    order = _order("o1")
    orders.add(order)

    fetched = orders.get("o1")

    assert fetched == order
    assert fetched.total_cents == 4498  # type: ignore[union-attr]


def test_unknown_order_is_none(repos: Repos) -> None:
    orders, _ = repos

    assert orders.get("ghost") is None


def test_update_persists_status_change(repos: Repos) -> None:
    orders, customers = repos
    customers.add(ADA)
    order = _order("o1")
    orders.add(order)

    order.status = OrderStatus.REFUNDED
    orders.update(order)

    assert orders.get("o1").status is OrderStatus.REFUNDED  # type: ignore[union-attr]


def test_for_customer_is_ordered_and_scoped(repos: Repos) -> None:
    orders, customers = repos
    customers.add(ADA)
    customers.add(Customer(customer_id="bob", name="Bob", email="bob@example.com"))
    orders.add(_order("o1"))
    orders.add(_order("o2"))
    orders.add(_order("other", customer_id="bob"))

    ada_orders = orders.for_customer("ada")

    assert [order.order_id for order in ada_orders] == ["o1", "o2"]
