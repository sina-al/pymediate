"""SQLite schema owned by the local persistence adapter."""

import aiosqlite


async def create_schema(connection: aiosqlite.Connection) -> None:
    """Create the process-local persistence schema."""
    await connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            lines_json TEXT NOT NULL,
            total_pence INTEGER NOT NULL,
            placed_on TEXT NOT NULL,
            refunded_pence INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            store_credit_pence INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            total_pence INTEGER NOT NULL,
            document_url TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS statements (
            statement_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            currency TEXT NOT NULL,
            order_count INTEGER NOT NULL,
            total_minor INTEGER NOT NULL,
            document_url TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identity_sequences (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS domain_event_journal (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            occurred_at TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS domain_event_journal_aggregate
            ON domain_event_journal (aggregate_type, aggregate_id, sequence);
        CREATE TABLE IF NOT EXISTS outbox_messages (
            message_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            occurred_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            trace_context_json TEXT NOT NULL,
            published_at TEXT,
            lease_until TEXT,
            lease_token TEXT
        );
        CREATE TABLE IF NOT EXISTS inbox_messages (
            message_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            lease_until TEXT,
            lease_token TEXT,
            processed_at TEXT
        );
        """
    )
    await connection.commit()
