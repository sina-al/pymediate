"""Fixtures that hand the contract suite every available port implementation.

The in-memory adapter always runs. Postgres and Neo4j join in when the corresponding
environment variables point at live services (compose provides them — see the README's
"Testing the adapters for real" section); otherwise those parameters skip. Same tests,
three databases: that's what "the adapters are interchangeable" means, executably.
"""

import os
from collections.abc import Iterator

import pytest

from shop_ports.customers import CustomerRepository
from shop_ports.orders import OrderRepository

Repos = tuple[OrderRepository, CustomerRepository]

POSTGRES_ENV = "SHOP_TEST_DATABASE_URL"
NEO4J_ENV = "SHOP_TEST_NEO4J_URI"


def _memory_repos() -> Iterator[Repos]:
    from shop_adapter_memory.repositories import (
        MemoryCustomerRepository,
        MemoryOrderRepository,
    )

    yield MemoryOrderRepository(), MemoryCustomerRepository()


def _postgres_repos() -> Iterator[Repos]:
    from shop_adapter_postgres.repositories import (
        PostgresCustomerRepository,
        PostgresOrderRepository,
        create_pool,
    )
    from shop_adapter_postgres.schema import ensure_schema

    pool = create_pool(os.environ[POSTGRES_ENV])
    try:
        ensure_schema(pool)
        with pool.connection() as conn:
            conn.execute("TRUNCATE orders, customers")
        yield PostgresOrderRepository(pool), PostgresCustomerRepository(pool)
    finally:
        pool.close()


def _neo4j_repos() -> Iterator[Repos]:
    from shop_adapter_neo4j.repositories import (
        Neo4jCustomerRepository,
        Neo4jOrderRepository,
        create_driver,
    )

    driver = create_driver(
        os.environ[NEO4J_ENV],
        os.environ.get("SHOP_TEST_NEO4J_USER", "neo4j"),
        os.environ.get("SHOP_TEST_NEO4J_PASSWORD", "shopshop"),
    )
    try:
        driver.execute_query("MATCH (n) DETACH DELETE n")
        yield Neo4jOrderRepository(driver), Neo4jCustomerRepository(driver)
    finally:
        driver.close()


@pytest.fixture(
    params=[
        pytest.param(_memory_repos, id="memory"),
        pytest.param(
            _postgres_repos,
            id="postgres",
            marks=pytest.mark.skipif(
                POSTGRES_ENV not in os.environ,
                reason=f"set {POSTGRES_ENV} to run the contract against Postgres",
            ),
        ),
        pytest.param(
            _neo4j_repos,
            id="neo4j",
            marks=pytest.mark.skipif(
                NEO4J_ENV not in os.environ,
                reason=f"set {NEO4J_ENV} to run the contract against Neo4j",
            ),
        ),
    ]
)
def repos(request: pytest.FixtureRequest) -> Iterator[Repos]:
    yield from request.param()
