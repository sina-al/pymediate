"""SQLite implementation of the shop's local persistence ports."""

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from datetime import UTC, date, datetime, timedelta
from types import TracebackType
from typing import Any, Self

import aiosqlite

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

from .sqlite_schema import create_schema


class SqliteDbGateway(
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
    """Provide zero-setup relational persistence with an in-memory SQLite database."""

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        self._connection: aiosqlite.Connection | None = None
        self._initialization_lock = asyncio.Lock()
        self._transaction_lock = asyncio.Lock()
        self._transaction_context: ContextVar[object | None] = ContextVar(
            "shop_sqlite_transaction_context", default=None
        )
        self._transaction_owner: asyncio.Task[Any] | None = None
        self._transaction_marker: object | None = None
        self._transaction_token: Token[object | None] | None = None

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

    async def _ensure_connection(self) -> aiosqlite.Connection:
        if self._connection is not None:
            return self._connection
        async with self._initialization_lock:
            if self._connection is not None:
                return self._connection
            connection = await aiosqlite.connect(self._path, isolation_level=None)
            connection.row_factory = sqlite3.Row
            try:
                await create_schema(connection)
            except BaseException:
                await connection.close()
                raise
            self._connection = connection
            return connection

    @asynccontextmanager
    async def _access(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await self._ensure_connection()
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("SQLite persistence requires an asyncio task")
        if task is self._transaction_owner:
            yield connection
            return
        inherited = self._transaction_context.get()
        if inherited is not None and inherited is self._transaction_marker:
            raise RuntimeError("SQLite transaction access cannot move to a child task")
        async with self._transaction_lock:
            yield connection

    @asynccontextmanager
    async def _standalone_transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("SQLite persistence requires an asyncio task")
        inherited = self._transaction_context.get()
        if task is self._transaction_owner or (
            inherited is not None and inherited is self._transaction_marker
        ):
            raise RuntimeError("lease operations cannot join an application transaction")
        connection = await self._ensure_connection()
        async with self._transaction_lock:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                await connection.rollback()
                raise
            else:
                await connection.commit()

    async def _execute(self, sql: str, parameters: tuple[object, ...] = ()) -> int:
        async with self._access() as connection:
            cursor = await connection.execute(sql, parameters)
            try:
                return cursor.rowcount
            finally:
                await cursor.close()

    async def _fetchone(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Row | None:
        async with self._access() as connection:
            cursor = await connection.execute(sql, parameters)
            try:
                return await cursor.fetchone()
            finally:
                await cursor.close()

    async def _fetchall(self, sql: str, parameters: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        async with self._access() as connection:
            cursor = await connection.execute(sql, parameters)
            try:
                return list(await cursor.fetchall())
            finally:
                await cursor.close()

    async def _begin(self) -> None:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("SQLite unit of work requires an asyncio task")
        if self._transaction_context.get() is not None:
            raise RuntimeError("SQLite unit of work cannot be nested or moved to a child task")
        await self._transaction_lock.acquire()
        try:
            connection = await self._ensure_connection()
            await connection.execute("BEGIN IMMEDIATE")
        except BaseException:
            self._transaction_lock.release()
            raise
        marker = object()
        self._transaction_owner = task
        self._transaction_marker = marker
        self._transaction_token = self._transaction_context.set(marker)

    async def _finish(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        task = asyncio.current_task()
        if task is not self._transaction_owner:
            raise RuntimeError("SQLite unit of work must exit from the task that entered it")
        try:
            connection = await self._ensure_connection()
            if exc_type is None:
                await connection.commit()
            else:
                await connection.rollback()
        finally:
            assert self._transaction_token is not None
            self._transaction_context.reset(self._transaction_token)
            self._transaction_token = None
            self._transaction_marker = None
            self._transaction_owner = None
            self._transaction_lock.release()

    async def close(self) -> None:
        """Close the SQLite connection when the application shuts down."""
        if asyncio.current_task() is self._transaction_owner:
            raise RuntimeError("SQLite database cannot close inside an active transaction")
        async with self._transaction_lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None

    async def next_order_identity(self) -> int:
        return await self._next_sequence_value("orders")

    async def insert_order(self, order: Order) -> None:
        lines = [
            {"sku": line.sku, "quantity": line.quantity, "unit_price_pence": line.unit_price_pence}
            for line in order.lines
        ]
        await self._execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                order.order_id,
                order.customer_id,
                json.dumps(lines),
                order.total_pence,
                order.placed_on.isoformat(),
                order.refunded_pence,
                order.status.value,
            ),
        )

    async def get_order(self, order_id: int) -> Order:
        row = await self._fetchone("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if row is None:
            raise OrderNotFoundError(order_id)
        return self._order_from_row(row)

    async def replace_order(self, order: Order) -> None:
        await self._execute(
            "UPDATE orders SET refunded_pence = ?, status = ? WHERE order_id = ?",
            (order.refunded_pence, order.status.value, order.order_id),
        )

    async def stream_orders(self, customer_id: int) -> AsyncIterator[Order]:
        rows = await self._fetchall(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY order_id", (customer_id,)
        )
        for row in rows:
            yield self._order_from_row(row)

    async def stream_orders_for_month(
        self, customer_id: int, year: int, month: int
    ) -> AsyncIterator[Order]:
        rows = await self._fetchall(
            """SELECT * FROM orders WHERE customer_id = ?
               AND substr(placed_on, 1, 7) = ? ORDER BY order_id""",
            (customer_id, f"{year:04d}-{month:02d}"),
        )
        for row in rows:
            yield self._order_from_row(row)

    async def append(self, event: DomainEvent) -> DomainEventRecord:
        record = DomainEventRecord.from_event(event)
        await self._execute(
            """INSERT INTO domain_event_journal
               (event_id, event_type, schema_version, occurred_at, aggregate_type,
                aggregate_id, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.event_id,
                record.event_type,
                record.schema_version,
                record.occurred_at.isoformat(),
                record.aggregate_type.value,
                record.aggregate_id,
                json.dumps(record.payload),
            ),
        )
        return record

    async def stream_domain_events(
        self, aggregate_type: AggregateType, aggregate_id: str
    ) -> AsyncIterator[DomainEventRecord]:
        rows = await self._fetchall(
            """SELECT event_id, event_type, schema_version, occurred_at, aggregate_type,
                      aggregate_id, payload_json
               FROM domain_event_journal
               WHERE aggregate_type = ? AND aggregate_id = ? ORDER BY sequence""",
            (aggregate_type.value, aggregate_id),
        )
        for row in rows:
            yield DomainEventRecord(
                event_id=str(row["event_id"]),
                event_type=str(row["event_type"]),
                schema_version=int(row["schema_version"]),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                aggregate_type=AggregateType(str(row["aggregate_type"])),
                aggregate_id=str(row["aggregate_id"]),
                payload=json.loads(str(row["payload_json"])),
            )

    async def get_customer(self, customer_id: int) -> CustomerAccount:
        row = await self._fetchone(
            "SELECT store_credit_pence FROM customers WHERE customer_id = ?", (customer_id,)
        )
        if row is None:
            raise CustomerNotFoundError(customer_id)
        return CustomerAccount(customer_id, int(row["store_credit_pence"]))

    async def insert_customer(self, customer: CustomerAccount) -> None:
        try:
            await self._execute(
                "INSERT INTO customers VALUES (?, ?)",
                (customer.customer_id, customer.store_credit_pence),
            )
        except sqlite3.IntegrityError:
            raise CustomerAlreadyExistsError(customer.customer_id) from None

    async def replace_customer(self, customer: CustomerAccount) -> None:
        rowcount = await self._execute(
            """UPDATE customers SET store_credit_pence = ? WHERE customer_id = ?""",
            (customer.store_credit_pence, customer.customer_id),
        )
        if rowcount == 0:
            raise CustomerNotFoundError(customer.customer_id)

    async def has_open_orders(self, customer_id: int) -> bool:
        row = await self._fetchone(
            """SELECT EXISTS(SELECT 1 FROM orders WHERE customer_id = ? AND status IN (?, ?))""",
            (customer_id, OrderStatus.PLACED.value, OrderStatus.PARTIALLY_REFUNDED.value),
        )
        assert row is not None
        return bool(row[0])

    async def delete_customer(self, customer_id: int) -> None:
        rowcount = await self._execute(
            "DELETE FROM customers WHERE customer_id = ?", (customer_id,)
        )
        if rowcount == 0:
            raise CustomerNotFoundError(customer_id)

    async def next_invoice_identity(self) -> int:
        return await self._next_sequence_value("invoices")

    async def insert_invoice(self, invoice: Invoice) -> None:
        await self._execute(
            "INSERT INTO invoices VALUES (?, ?, ?, ?, ?)",
            (
                invoice.invoice_id,
                invoice.order_id,
                invoice.customer_id,
                invoice.total_pence,
                invoice.document_url,
            ),
        )

    async def get_invoice_for_order(self, order_id: int) -> Invoice:
        row = await self._fetchone("SELECT * FROM invoices WHERE order_id = ?", (order_id,))
        if row is None:
            raise InvoiceNotFoundError(order_id)
        return Invoice(
            int(row["invoice_id"]),
            int(row["order_id"]),
            int(row["customer_id"]),
            int(row["total_pence"]),
            str(row["document_url"]),
        )

    async def next_statement_identity(self) -> int:
        return await self._next_sequence_value("statements")

    async def insert_statement(self, statement: MonthlyStatement) -> None:
        await self._execute(
            "INSERT INTO statements VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
        await self._execute(
            """INSERT INTO outbox_messages
               (message_id, event_type, schema_version, occurred_at, payload_json,
                trace_context_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                message.message_id,
                message.event_type,
                message.schema_version,
                message.occurred_at.isoformat(),
                json.dumps(message.payload),
                json.dumps(outbox.trace_context),
            ),
        )

    async def claim_outbox_messages(
        self, limit: int, lease_seconds: int
    ) -> tuple[OutboxClaim, ...]:
        now = datetime.now(UTC)
        lease_until = (now + timedelta(seconds=lease_seconds)).isoformat()
        async with self._standalone_transaction() as connection:
            cursor = await connection.execute(
                """SELECT * FROM outbox_messages
                   WHERE published_at IS NULL AND (lease_until IS NULL OR lease_until <= ?)
                   ORDER BY occurred_at, message_id LIMIT ?""",
                (now.isoformat(), limit),
            )
            try:
                rows = list(await cursor.fetchall())
            finally:
                await cursor.close()
            tokens = {str(row["message_id"]): LeaseToken.create() for row in rows}
            await connection.executemany(
                """UPDATE outbox_messages SET lease_until = ?, lease_token = ?
                   WHERE message_id = ? AND published_at IS NULL
                     AND (lease_until IS NULL OR lease_until <= ?)""",
                [
                    (
                        lease_until,
                        str(tokens[str(row["message_id"])]),
                        row["message_id"],
                        now.isoformat(),
                    )
                    for row in rows
                ],
            )
        return tuple(
            OutboxClaim(
                OutboxMessage(
                    IntegrationMessage(
                        message_id=str(row["message_id"]),
                        event_type=str(row["event_type"]),
                        schema_version=int(row["schema_version"]),
                        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                        payload=json.loads(str(row["payload_json"])),
                    ),
                    json.loads(str(row["trace_context_json"])),
                ),
                tokens[str(row["message_id"])],
            )
            for row in rows
        )

    async def renew_outbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        now = datetime.now(UTC)
        rowcount = await self._execute(
            """UPDATE outbox_messages SET lease_until = ?
               WHERE message_id = ? AND published_at IS NULL AND lease_token = ?
                 AND lease_until > ?""",
            (
                (now + timedelta(seconds=lease_seconds)).isoformat(),
                message_id,
                str(lease_token),
                now.isoformat(),
            ),
        )
        return rowcount == 1

    async def mark_outbox_message_published(self, message_id: str, lease_token: LeaseToken) -> bool:
        now = datetime.now(UTC)
        rowcount = await self._execute(
            """UPDATE outbox_messages
               SET published_at = ?, lease_until = NULL, lease_token = NULL
               WHERE message_id = ? AND published_at IS NULL AND lease_token = ?
                 AND lease_until > ?""",
            (now.isoformat(), message_id, str(lease_token), now.isoformat()),
        )
        return rowcount == 1

    async def release_outbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        rowcount = await self._execute(
            """UPDATE outbox_messages SET lease_until = NULL, lease_token = NULL
               WHERE message_id = ? AND published_at IS NULL AND lease_token = ?""",
            (message_id, str(lease_token)),
        )
        return rowcount == 1

    async def claim_inbox_message(self, message_id: str, lease_seconds: int) -> InboxClaim:
        now = datetime.now(UTC)
        lease_until = (now + timedelta(seconds=lease_seconds)).isoformat()
        lease_token = LeaseToken.create()
        async with self._standalone_transaction() as connection:
            cursor = await connection.execute(
                """INSERT INTO inbox_messages (message_id, state, lease_until, lease_token)
                   VALUES (?, 'processing', ?, ?)
                   ON CONFLICT(message_id) DO UPDATE
                   SET state = 'processing', lease_until = excluded.lease_until,
                       lease_token = excluded.lease_token
                   WHERE inbox_messages.state = 'processing'
                     AND (inbox_messages.lease_until IS NULL OR inbox_messages.lease_until <= ?)""",
                (message_id, lease_until, str(lease_token), now.isoformat()),
            )
            try:
                claimed = cursor.rowcount == 1
            finally:
                await cursor.close()
            if claimed:
                return InboxClaim.process(lease_token)
            cursor = await connection.execute(
                "SELECT state FROM inbox_messages WHERE message_id = ?", (message_id,)
            )
            try:
                row = await cursor.fetchone()
            finally:
                await cursor.close()
        assert row is not None
        return InboxClaim.processed() if row["state"] == "processed" else InboxClaim.busy()

    async def renew_inbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        now = datetime.now(UTC)
        rowcount = await self._execute(
            """UPDATE inbox_messages SET lease_until = ?
               WHERE message_id = ? AND state = 'processing' AND lease_token = ?
                 AND lease_until > ?""",
            (
                (now + timedelta(seconds=lease_seconds)).isoformat(),
                message_id,
                str(lease_token),
                now.isoformat(),
            ),
        )
        return rowcount == 1

    async def complete_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        now = datetime.now(UTC)
        rowcount = await self._execute(
            """UPDATE inbox_messages
               SET state = 'processed', lease_until = NULL, lease_token = NULL, processed_at = ?
               WHERE message_id = ? AND state = 'processing' AND lease_token = ?
                 AND lease_until > ?""",
            (now.isoformat(), message_id, str(lease_token), now.isoformat()),
        )
        return rowcount == 1

    async def release_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        rowcount = await self._execute(
            """DELETE FROM inbox_messages
               WHERE message_id = ? AND state = 'processing' AND lease_token = ?""",
            (message_id, str(lease_token)),
        )
        return rowcount == 1

    async def orders(self) -> list[Order]:
        """Return persisted orders for focused adapter assertions in tests."""
        return [
            self._order_from_row(row)
            for row in await self._fetchall("SELECT * FROM orders ORDER BY order_id")
        ]

    async def customers(self) -> list[CustomerAccount]:
        """Return persisted customers for focused adapter assertions in tests."""
        rows = await self._fetchall("SELECT * FROM customers ORDER BY customer_id")
        return [
            CustomerAccount(int(row["customer_id"]), int(row["store_credit_pence"])) for row in rows
        ]

    async def statements(self) -> list[MonthlyStatement]:
        """Return persisted statements for focused adapter assertions in tests."""
        rows = await self._fetchall("SELECT * FROM statements ORDER BY statement_id")
        return [
            MonthlyStatement(
                int(row["statement_id"]),
                int(row["customer_id"]),
                int(row["year"]),
                int(row["month"]),
                str(row["currency"]),
                int(row["order_count"]),
                int(row["total_minor"]),
                str(row["document_url"]),
            )
            for row in rows
        ]

    async def _next_sequence_value(self, name: str) -> int:
        async def increment(connection: aiosqlite.Connection) -> int:
            cursor = await connection.execute(
                """INSERT INTO identity_sequences (name, value) VALUES (?, 1)
                   ON CONFLICT(name) DO UPDATE SET value = value + 1
                   RETURNING value""",
                (name,),
            )
            try:
                row = await cursor.fetchone()
            finally:
                await cursor.close()
            assert row is not None
            return int(row[0])

        if asyncio.current_task() is self._transaction_owner:
            connection = await self._ensure_connection()
            return await increment(connection)
        async with self._standalone_transaction() as connection:
            return await increment(connection)

    @staticmethod
    def _order_from_row(row: sqlite3.Row) -> Order:
        lines = tuple(
            OrderLine(item["sku"], item["quantity"], item["unit_price_pence"])
            for item in json.loads(str(row["lines_json"]))
        )
        return Order(
            int(row["order_id"]),
            int(row["customer_id"]),
            lines,
            int(row["total_pence"]),
            date.fromisoformat(str(row["placed_on"])),
            int(row["refunded_pence"]),
            OrderStatus(str(row["status"])),
        )
