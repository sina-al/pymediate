"""The persistence ports on PostgreSQL.

Only this package (and the composition root that chooses it) knows SQL exists. The
core never imports psycopg; swap this package out and no other code changes.
"""
