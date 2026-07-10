"""The persistence ports on Neo4j.

The same `OrderRepository` and `CustomerRepository` protocols as the Postgres and
in-memory adapters — implemented as `(:Customer)-[:PLACED]->(:Order)` nodes and a
relationship. The core cannot tell the difference; that's the point.
"""
