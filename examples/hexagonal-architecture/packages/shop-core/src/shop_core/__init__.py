"""The application core: the shop's use cases, one request and one handler each.

This package holds everything the shop *does* — placing, cancelling, refunding, and
exporting orders; registering customers — organized by domain. It depends on the
domain's entities, the ports, and pymediate. It does not know Flask, Postgres, Neo4j,
Redis, or which of them is present at runtime; those arrive as port implementations,
handed to `bootstrap.build_mediator` by a composition root.
"""
