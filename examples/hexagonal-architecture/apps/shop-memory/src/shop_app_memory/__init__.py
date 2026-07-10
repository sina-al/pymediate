"""Composition root: the shop on in-memory adapters.

The only code in the memory variant that knows which implementations exist. About
forty lines of wiring — and the whole difference between this deployment and the
Postgres or Neo4j ones.
"""
