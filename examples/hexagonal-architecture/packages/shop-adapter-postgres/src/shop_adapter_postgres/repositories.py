"""Persistence ports on PostgreSQL."""

import json

from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from shop_domain.customers import Customer
from shop_domain.orders import LineItem, Order, OrderStatus


def _order_from_row(row: tuple[str, str, list[dict[str, object]] | str, str]) -> Order:
    order_id, customer_id, items, status = row
    raw_items = json.loads(items) if isinstance(items, str) else items
    return Order(
        order_id=order_id,
        customer_id=customer_id,
        items=[
            LineItem(
                sku=str(item["sku"]),
                quantity=int(item["quantity"]),  # type: ignore[arg-type]
                unit_price_cents=int(item["unit_price_cents"]),  # type: ignore[arg-type]
            )
            for item in raw_items
        ],
        status=OrderStatus(status),
    )


class PostgresOrderRepository:
    """OrderRepository on an orders table; items are a JSONB column."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def add(self, order: Order) -> None:
        items = [
            {"sku": i.sku, "quantity": i.quantity, "unit_price_cents": i.unit_price_cents}
            for i in order.items
        ]
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO orders (order_id, customer_id, items, status) VALUES (%s, %s, %s, %s)",
                (order.order_id, order.customer_id, Jsonb(items), order.status.value),
            )

    def get(self, order_id: str) -> Order | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT order_id, customer_id, items, status FROM orders WHERE order_id = %s",
                (order_id,),
                # tuple_row keeps _order_from_row indifferent to psycopg's row factories.
            ).fetchone()
        return None if row is None else _order_from_row(row)

    def update(self, order: Order) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "UPDATE orders SET status = %s WHERE order_id = %s",
                (order.status.value, order.order_id),
            )

    def for_customer(self, customer_id: str) -> list[Order]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT order_id, customer_id, items, status FROM orders "
                "WHERE customer_id = %s ORDER BY placed_at",
                (customer_id,),
            ).fetchall()
        return [_order_from_row(row) for row in rows]


class PostgresCustomerRepository:
    """CustomerRepository on a customers table."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def add(self, customer: Customer) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO customers (customer_id, name, email, store_credit_cents) "
                "VALUES (%s, %s, %s, %s)",
                (
                    customer.customer_id,
                    customer.name,
                    customer.email,
                    customer.store_credit_cents,
                ),
            )

    def get(self, customer_id: str) -> Customer | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT customer_id, name, email, store_credit_cents FROM customers "
                "WHERE customer_id = %s",
                (customer_id,),
            ).fetchone()
        if row is None:
            return None
        return Customer(customer_id=row[0], name=row[1], email=row[2], store_credit_cents=row[3])

    def credit(self, customer_id: str, amount_cents: int) -> Customer | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "UPDATE customers SET store_credit_cents = store_credit_cents + %s "
                "WHERE customer_id = %s "
                "RETURNING customer_id, name, email, store_credit_cents",
                (amount_cents, customer_id),
            ).fetchone()
        if row is None:
            return None
        return Customer(customer_id=row[0], name=row[1], email=row[2], store_credit_cents=row[3])


def create_pool(dsn: str) -> ConnectionPool:
    """Open a connection pool with tuple rows (what the repositories expect)."""
    return ConnectionPool(dsn, kwargs={"row_factory": tuple_row}, open=True)
