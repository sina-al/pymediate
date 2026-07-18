# Deployment smoke tests

These tests treat a running Shop deployment as a black box. They do not construct a container,
replace providers, or import application implementations.

The complete order test crosses the HTTP adapter, mediator, PostgreSQL transaction and outbox,
relay, selected cloud queue, worker, mediator again, selected object storage, and invoice query.
It therefore detects broken wiring and infrastructure integration that an in-process API test
cannot see.

Start a deployment and run its smoke tests:

```console
uv run poe compose:up --cloud aws
uv run poe compose:smoke --cloud aws
```

Replace `aws` with `azure` for the Azure profile. Set `SHOP_SMOKE_BASE_URL` to target an API
other than `http://localhost:8000`.
