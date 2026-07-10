"""Persistence ports on Neo4j."""

import json
from typing import Any

from neo4j import Driver, GraphDatabase

from shop_domain.customers import Customer
from shop_domain.orders import LineItem, Order, OrderStatus


def _order_from_node(node: dict[str, Any], customer_id: str) -> Order:
    return Order(
        order_id=node["order_id"],
        customer_id=customer_id,
        items=[
            LineItem(
                sku=item["sku"],
                quantity=item["quantity"],
                unit_price_cents=item["unit_price_cents"],
            )
            # Neo4j properties can't hold nested maps, so items travel as a JSON string.
            for item in json.loads(node["items"])
        ],
        status=OrderStatus(node["status"]),
    )


class Neo4jOrderRepository:
    """OrderRepository as (:Customer)-[:PLACED]->(:Order) in the graph."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    def add(self, order: Order) -> None:
        items = json.dumps(
            [
                {"sku": i.sku, "quantity": i.quantity, "unit_price_cents": i.unit_price_cents}
                for i in order.items
            ]
        )
        self._driver.execute_query(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "CREATE (c)-[:PLACED]->(:Order {order_id: $order_id, items: $items, "
            "status: $status, placed_at: timestamp()})",
            customer_id=order.customer_id,
            order_id=order.order_id,
            items=items,
            status=order.status.value,
        )

    def get(self, order_id: str) -> Order | None:
        records, _, _ = self._driver.execute_query(
            "MATCH (c:Customer)-[:PLACED]->(o:Order {order_id: $order_id}) "
            "RETURN o, c.customer_id AS customer_id",
            order_id=order_id,
        )
        if not records:
            return None
        record = records[0]
        return _order_from_node(dict(record["o"]), record["customer_id"])

    def update(self, order: Order) -> None:
        self._driver.execute_query(
            "MATCH (o:Order {order_id: $order_id}) SET o.status = $status",
            order_id=order.order_id,
            status=order.status.value,
        )

    def for_customer(self, customer_id: str) -> list[Order]:
        records, _, _ = self._driver.execute_query(
            "MATCH (c:Customer {customer_id: $customer_id})-[:PLACED]->(o:Order) "
            "RETURN o ORDER BY o.placed_at",
            customer_id=customer_id,
        )
        return [_order_from_node(dict(record["o"]), customer_id) for record in records]


class Neo4jCustomerRepository:
    """CustomerRepository as (:Customer) nodes."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    def add(self, customer: Customer) -> None:
        self._driver.execute_query(
            "CREATE (:Customer {customer_id: $customer_id, name: $name, email: $email, "
            "store_credit_cents: $store_credit_cents})",
            customer_id=customer.customer_id,
            name=customer.name,
            email=customer.email,
            store_credit_cents=customer.store_credit_cents,
        )

    def get(self, customer_id: str) -> Customer | None:
        records, _, _ = self._driver.execute_query(
            "MATCH (c:Customer {customer_id: $customer_id}) RETURN c",
            customer_id=customer_id,
        )
        return None if not records else self._from_node(dict(records[0]["c"]))

    def credit(self, customer_id: str, amount_cents: int) -> Customer | None:
        records, _, _ = self._driver.execute_query(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "SET c.store_credit_cents = c.store_credit_cents + $amount_cents RETURN c",
            customer_id=customer_id,
            amount_cents=amount_cents,
        )
        return None if not records else self._from_node(dict(records[0]["c"]))

    @staticmethod
    def _from_node(node: dict[str, Any]) -> Customer:
        return Customer(
            customer_id=node["customer_id"],
            name=node["name"],
            email=node["email"],
            store_credit_cents=node["store_credit_cents"],
        )


def create_driver(uri: str, user: str, password: str) -> Driver:
    """Open a driver and make sure the uniqueness constraints exist."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.execute_query(
        "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS "
        "FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE"
    )
    driver.execute_query(
        "CREATE CONSTRAINT order_id_unique IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE"
    )
    return driver
