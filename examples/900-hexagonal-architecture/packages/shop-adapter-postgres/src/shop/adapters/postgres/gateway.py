"""PostgreSQL implementation of the shop's persistence ports."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextvars import ContextVar, Token
from datetime import date
from types import TracebackType
from typing import Any, Self

import psycopg
from psycopg_pool import AsyncConnectionPool

from shop.domain.entities.customers import CustomerAccount
from shop.domain.entities.invoices import Invoice
from shop.domain.entities.orders import Order, OrderLine, OrderStatus
from shop.domain.entities.statements import MonthlyStatement
from shop.domain.errors.customers import CustomerAlreadyExistsError, CustomerNotFoundError
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.errors.orders import OrderNotFoundError
from shop.domain.events.base import AggregateType, DomainEvent
from shop.ports.audit import DomainEventJournal, DomainEventJournalReader, DomainEventRecord
from shop.ports.customers.adjust_store_credit import AdjustStoreCreditDbGateway
from shop.ports.customers.close_customer_account import (
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
)
from shop.ports.customers.open_customer_account import OpenCustomerAccountDbGateway
from shop.ports.inbox import InboxClaim, MessageInbox
from shop.ports.integration import IntegrationMessage
from shop.ports.invoices.create_invoice import CreateInvoiceDbGateway
from shop.ports.invoices.get_invoice import GetInvoiceDbGateway
from shop.ports.leases import LeaseToken
from shop.ports.orders.cancel_order import CancelOrderDbGateway
from shop.ports.orders.create_order import CreateOrderDbGateway
from shop.ports.orders.export_orders import ExportOrdersDbGateway
from shop.ports.orders.refund_order import RefundOrderDbGateway
from shop.ports.outbox import OutboxClaim, OutboxMessage, OutboxRelaySource, OutboxWriter
from shop.ports.statements.create_monthly_statement import CreateMonthlyStatementDbGateway

from .schema import ensure_schema


class _CursorContext:
    def __init__(self, database: "PostgresDbGateway") -> None:
        self._database = database
        self._connection_context: Any = None
        self._cursor_context: Any = None

    async def __aenter__(self) -> Any:
        await self._database._ensure_connection()
        binding = self._database._current_transaction.get()
        if binding is None:
            self._connection_context = self._database._pool.connection()
            connection = await self._connection_context.__aenter__()
        else:
            if asyncio.current_task() is not binding.owner:
                raise RuntimeError("PostgreSQL transaction access cannot move to a child task")
            connection = binding.connection
        self._cursor_context = connection.cursor()
        return await self._cursor_context.__aenter__()

    async def __aexit__(self, *exc: object) -> None:
        await self._cursor_context.__aexit__(*exc)
        if self._connection_context is not None:
            await self._connection_context.__aexit__(*exc)


class _ConnectionFacade:
    def __init__(self, database: "PostgresDbGateway") -> None:
        self._database = database

    def cursor(self) -> _CursorContext:
        return _CursorContext(self._database)


class _TransactionHandle:
    def __init__(
        self,
        connection_context: Any,
        transaction_context: Any,
        token: Token["_TransactionBinding | None"],
        binding: "_TransactionBinding",
    ) -> None:
        self.connection_context = connection_context
        self.transaction_context = transaction_context
        self.token = token
        self.binding = binding


class _TransactionBinding:
    def __init__(
        self,
        connection: psycopg.AsyncConnection[tuple[Any, ...]],
        owner: asyncio.Task[Any],
    ) -> None:
        self.connection = connection
        self.owner = owner


class PostgresDbGateway(
    CreateOrderDbGateway,
    CancelOrderDbGateway,
    RefundOrderDbGateway,
    ExportOrdersDbGateway,
    AdjustStoreCreditDbGateway,
    OpenCustomerAccountDbGateway,
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
    CreateInvoiceDbGateway,
    GetInvoiceDbGateway,
    CreateMonthlyStatementDbGateway,
    DomainEventJournalReader,
    DomainEventJournal,
    OutboxWriter,
    OutboxRelaySource,
    MessageInbox,
):
    """Implement the shop's database, event journal, and durable-job gateway ports."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool = AsyncConnectionPool[psycopg.AsyncConnection[tuple[Any, ...]]](
            dsn,
            open=False,
            kwargs={"autocommit": True},
        )
        self._current_transaction: ContextVar[_TransactionBinding | None] = ContextVar(
            "shop_postgres_transaction", default=None
        )
        self._connection = _ConnectionFacade(self)
        self._schema_ready = False
        self._initialization_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        await self._ensure_connection()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    @classmethod
    async def connect(cls, dsn: str) -> Self:
        """Connect and ensure the example persistence schema exists."""
        instance = cls(dsn)
        await instance._ensure_connection()
        return instance

    async def _ensure_connection(self) -> None:
        if self._schema_ready:
            return
        async with self._initialization_lock:
            if self._schema_ready:
                return
            await self._pool.open()
            connection_context = self._pool.connection()
            connection = await connection_context.__aenter__()
            try:
                await ensure_schema(connection)
            except BaseException as exc:
                await connection_context.__aexit__(type(exc), exc, exc.__traceback__)
                await self._pool.close()
                raise
            else:
                await connection_context.__aexit__(None, None, None)
            self._schema_ready = True

    async def _begin(self) -> _TransactionHandle:
        await self._ensure_connection()
        if self._current_transaction.get() is not None:
            raise RuntimeError("PostgreSQL unit of work cannot be nested or moved to a child task")
        owner = asyncio.current_task()
        if owner is None:
            raise RuntimeError("PostgreSQL unit of work requires an asyncio task")
        connection_context = self._pool.connection()
        connection = await connection_context.__aenter__()
        transaction_context = connection.transaction()
        try:
            await transaction_context.__aenter__()
        except BaseException as exc:
            await connection_context.__aexit__(type(exc), exc, exc.__traceback__)
            raise
        binding = _TransactionBinding(connection, owner)
        token = self._current_transaction.set(binding)
        return _TransactionHandle(connection_context, transaction_context, token, binding)

    async def _finish(
        self,
        handle: _TransactionHandle,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if asyncio.current_task() is not handle.binding.owner:
            raise RuntimeError("PostgreSQL unit of work must exit from the task that entered it")
        try:
            await handle.transaction_context.__aexit__(exc_type, exc_value, traceback)
        finally:
            self._current_transaction.reset(handle.token)
            await handle.connection_context.__aexit__(exc_type, exc_value, traceback)

    async def next_order_identity(self) -> int:
        async with self._connection.cursor() as cursor:
            await cursor.execute("SELECT nextval(pg_get_serial_sequence('orders', 'order_id'))")
            row = await cursor.fetchone()
        assert row is not None
        return int(row[0])

    async def insert_order(self, order: Order) -> None:
        lines = [
            {
                "sku": line.sku,
                "quantity": line.quantity,
                "unit_price_pence": line.unit_price_pence,
            }
            for line in order.lines
        ]
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO orders
                    (order_id, customer_id, lines_json, total_pence, placed_on,
                     refunded_pence, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    order.order_id,
                    order.customer_id,
                    json.dumps(lines),
                    order.total_pence,
                    order.placed_on,
                    order.refunded_pence,
                    order.status,
                ),
            )

    async def get_order(self, order_id: int) -> Order:
        await self._ensure_connection()
        lock = " FOR UPDATE" if self._current_transaction.get() is not None else ""
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT order_id, customer_id, lines_json, total_pence, placed_on,
                          refunded_pence, status
                   FROM orders WHERE order_id = %s"""
                + lock,
                (order_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise OrderNotFoundError(order_id)
        return self._order_from_row(row)

    async def replace_order(self, order: Order) -> None:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE orders SET refunded_pence = %s, status = %s WHERE order_id = %s",
                (order.refunded_pence, order.status, order.order_id),
            )

    async def stream_orders(self, customer_id: int) -> AsyncIterator[Order]:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT order_id, customer_id, lines_json, total_pence, placed_on,
                          refunded_pence, status
                   FROM orders WHERE customer_id = %s ORDER BY order_id""",
                (customer_id,),
            )
            async for row in cursor:
                yield self._order_from_row(row)

    async def stream_orders_for_month(
        self, customer_id: int, year: int, month: int
    ) -> AsyncIterator[Order]:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT order_id, customer_id, lines_json, total_pence, placed_on,
                          refunded_pence, status
                   FROM orders
                   WHERE customer_id = %s
                     AND EXTRACT(YEAR FROM placed_on) = %s
                     AND EXTRACT(MONTH FROM placed_on) = %s
                   ORDER BY order_id""",
                (customer_id, year, month),
            )
            async for row in cursor:
                yield self._order_from_row(row)

    async def append(self, event: DomainEvent) -> DomainEventRecord:
        record = DomainEventRecord.from_event(event)
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO domain_event_journal
                   (event_id, event_type, schema_version, occurred_at, aggregate_type,
                    aggregate_id, payload_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    record.event_id,
                    record.event_type,
                    record.schema_version,
                    record.occurred_at,
                    record.aggregate_type.value,
                    record.aggregate_id,
                    json.dumps(record.payload),
                ),
            )
        return record

    async def stream_domain_events(
        self, aggregate_type: AggregateType, aggregate_id: str
    ) -> AsyncIterator[DomainEventRecord]:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT event_id, event_type, schema_version, occurred_at, aggregate_type,
                          aggregate_id, payload_json
                   FROM domain_event_journal
                   WHERE aggregate_type = %s AND aggregate_id = %s ORDER BY sequence""",
                (aggregate_type.value, aggregate_id),
            )
            rows = await cursor.fetchall()
        for row in rows:
            yield DomainEventRecord(
                event_id=str(row[0]),
                event_type=str(row[1]),
                schema_version=int(row[2]),
                occurred_at=row[3],
                aggregate_type=AggregateType(str(row[4])),
                aggregate_id=str(row[5]),
                payload=dict(row[6]),
            )

    async def get_customer(self, customer_id: int) -> CustomerAccount:
        lock = " FOR UPDATE" if self._current_transaction.get() is not None else ""
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "SELECT store_credit_pence FROM customers WHERE customer_id = %s" + lock,
                (customer_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise CustomerNotFoundError(customer_id)
        return CustomerAccount(customer_id, int(row[0]))

    async def insert_customer(self, customer: CustomerAccount) -> None:
        try:
            async with self._connection.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO customers VALUES (%s, %s)",
                    (customer.customer_id, customer.store_credit_pence),
                )
        except psycopg.errors.UniqueViolation:
            raise CustomerAlreadyExistsError(customer.customer_id) from None

    async def replace_customer(self, customer: CustomerAccount) -> None:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE customers SET store_credit_pence = %s
                   WHERE customer_id = %s""",
                (customer.store_credit_pence, customer.customer_id),
            )
            if cursor.rowcount == 0:
                raise CustomerNotFoundError(customer.customer_id)

    async def has_open_orders(self, customer_id: int) -> bool:
        await self._ensure_connection()
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT EXISTS(
                    SELECT 1 FROM orders
                    WHERE customer_id = %s AND status IN (%s, %s)
                )""",
                (customer_id, OrderStatus.PLACED, OrderStatus.PARTIALLY_REFUNDED),
            )
            row = await cursor.fetchone()
        assert row is not None
        return bool(row[0])

    async def delete_customer(self, customer_id: int) -> None:
        async with self._connection.cursor() as cursor:
            await cursor.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
            if cursor.rowcount == 0:
                raise CustomerNotFoundError(customer_id)

    async def next_invoice_identity(self) -> int:
        async with self._connection.cursor() as cursor:
            await cursor.execute("SELECT nextval(pg_get_serial_sequence('invoices', 'invoice_id'))")
            row = await cursor.fetchone()
        assert row is not None
        return int(row[0])

    async def insert_invoice(self, invoice: Invoice) -> None:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO invoices VALUES (%s, %s, %s, %s, %s)",
                (
                    invoice.invoice_id,
                    invoice.order_id,
                    invoice.customer_id,
                    invoice.total_pence,
                    invoice.document_url,
                ),
            )

    async def get_invoice_for_order(self, order_id: int) -> Invoice:
        await self._ensure_connection()
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """SELECT invoice_id, order_id, customer_id, total_pence, document_url
                   FROM invoices WHERE order_id = %s""",
                (order_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise InvoiceNotFoundError(order_id)
        return Invoice(int(row[0]), int(row[1]), int(row[2]), int(row[3]), str(row[4]))

    async def next_statement_identity(self) -> int:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "SELECT nextval(pg_get_serial_sequence('statements', 'statement_id'))"
            )
            row = await cursor.fetchone()
        assert row is not None
        return int(row[0])

    async def insert_statement(self, statement: MonthlyStatement) -> None:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO statements VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    statement.statement_id,
                    statement.customer_id,
                    statement.year,
                    statement.month,
                    statement.currency,
                    statement.order_count,
                    statement.total_minor,
                    statement.document_url,
                ),
            )

    async def insert_outbox_message(self, outbox: OutboxMessage) -> None:
        message = outbox.message
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO outbox_messages
                   (message_id, event_type, schema_version, occurred_at, payload_json,
                    trace_context_json)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    message.message_id,
                    message.event_type,
                    message.schema_version,
                    message.occurred_at,
                    json.dumps(message.payload),
                    json.dumps(outbox.trace_context),
                ),
            )

    async def claim_outbox_messages(
        self, limit: int, lease_seconds: int
    ) -> tuple[OutboxClaim, ...]:
        await self._ensure_connection()
        lease_token = LeaseToken.create()
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE outbox_messages
                   SET lease_until = NOW() + (%s * INTERVAL '1 second'), lease_token = %s
                   WHERE message_id IN (
                     SELECT message_id FROM outbox_messages
                     WHERE published_at IS NULL
                       AND (lease_until IS NULL OR lease_until <= NOW())
                     ORDER BY occurred_at, message_id
                     FOR UPDATE SKIP LOCKED LIMIT %s
                   )
                   RETURNING message_id, event_type, schema_version, occurred_at, payload_json,
                             trace_context_json""",
                (lease_seconds, lease_token.value, limit),
            )
            rows = await cursor.fetchall()
        return tuple(
            OutboxClaim(
                OutboxMessage(
                    IntegrationMessage(
                        message_id=str(row[0]),
                        event_type=str(row[1]),
                        schema_version=int(row[2]),
                        occurred_at=row[3],
                        payload=dict(row[4]),
                    ),
                    dict(row[5]),
                ),
                lease_token,
            )
            for row in sorted(rows, key=lambda row: (row[3], str(row[0])))
        )

    async def renew_outbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE outbox_messages
                   SET lease_until = NOW() + (%s * INTERVAL '1 second')
                   WHERE message_id = %s AND published_at IS NULL AND lease_token = %s
                     AND lease_until > NOW()""",
                (lease_seconds, message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def mark_outbox_message_published(self, message_id: str, lease_token: LeaseToken) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE outbox_messages
                   SET published_at = NOW(), lease_until = NULL, lease_token = NULL
                   WHERE message_id = %s AND published_at IS NULL AND lease_token = %s
                     AND lease_until > NOW()""",
                (message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def release_outbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE outbox_messages SET lease_until = NULL, lease_token = NULL
                   WHERE message_id = %s AND published_at IS NULL AND lease_token = %s""",
                (message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def claim_inbox_message(self, message_id: str, lease_seconds: int) -> InboxClaim:
        await self._ensure_connection()
        lease_token = LeaseToken.create()
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO inbox_messages (message_id, state, lease_until, lease_token)
                   VALUES (%s, 'processing', NOW() + (%s * INTERVAL '1 second'), %s)
                   ON CONFLICT (message_id) DO UPDATE
                   SET state = 'processing',
                       lease_until = NOW() + (%s * INTERVAL '1 second'),
                       lease_token = EXCLUDED.lease_token
                   WHERE inbox_messages.state = 'processing'
                     AND (inbox_messages.lease_until IS NULL OR inbox_messages.lease_until <= NOW())
                   RETURNING state""",
                (message_id, lease_seconds, lease_token.value, lease_seconds),
            )
            claimed = await cursor.fetchone()
            if claimed is not None:
                return InboxClaim.process(lease_token)
            await cursor.execute(
                "SELECT state FROM inbox_messages WHERE message_id = %s", (message_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return await self.claim_inbox_message(message_id, lease_seconds)
        return InboxClaim.processed() if row[0] == "processed" else InboxClaim.busy()

    async def renew_inbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE inbox_messages
                   SET lease_until = NOW() + (%s * INTERVAL '1 second')
                   WHERE message_id = %s AND state = 'processing' AND lease_token = %s
                     AND lease_until > NOW()""",
                (lease_seconds, message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def complete_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """UPDATE inbox_messages
                   SET state = 'processed', lease_until = NULL, lease_token = NULL,
                       processed_at = NOW()
                   WHERE message_id = %s AND state = 'processing' AND lease_token = %s
                     AND lease_until > NOW()""",
                (message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def release_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                """DELETE FROM inbox_messages
                   WHERE message_id = %s AND state = 'processing' AND lease_token = %s""",
                (message_id, lease_token.value),
            )
            return cursor.rowcount == 1

    async def close(self) -> None:
        """Close the connection pool when the application shuts down."""
        await self._pool.close()

    @staticmethod
    def _order_from_row(row: tuple[Any, ...]) -> Order:
        lines = tuple(
            OrderLine(item["sku"], item["quantity"], item["unit_price_pence"]) for item in row[2]
        )
        placed_on = row[4]
        assert isinstance(placed_on, date)
        return Order(
            int(row[0]),
            int(row[1]),
            lines,
            int(row[3]),
            placed_on,
            int(row[5]),
            OrderStatus(str(row[6])),
        )
