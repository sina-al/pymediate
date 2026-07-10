# hexagonal-architecture

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fhexagonal-architecture%2Fdevcontainer.json)

This is the shop from [*Nobody wants to touch that code*](https://pymediate.sina-al.uk/articles/nobody-wants-to-touch-that-code),
rebuilt the way the essay's ending promises: **the application core owns its interfaces,
and everything else — Postgres, Neo4j, Redis, Flask, the CLI — is a plug-in detail.**
One application; three interchangeable databases behind it; three doorways in front of
it; three Docker images, each containing only the dependencies its variant actually uses.

If you've read the article, this is the follow-up. If you haven't, everything below
still stands on its own.

## Run it

No Docker needed for the first taste:

```bash
cd examples/hexagonal-architecture
uv sync
uv run pytest
```

```text
33 passed, 16 skipped
```

(The skips are the Postgres/Neo4j contract tests waiting for live databases — they run
[further down](#testing-the-adapters-for-real).) Then a full session on the in-memory
variant:

```bash
uv run python -m shop_app_memory.cli demo
```

```text
Registered Ada (4ecf31504343448c91caf09c2ddf7f59)
Placed order f6c11ce0453540ffbac75df7eb58eadc for 3998 cents
Refunded 3998 cents via store_credit
Exported 1 orders to file:///tmp/shop-exports/orders-4ecf31504343448c91caf09c2ddf7f59.csv
```

## The layout

The directory tree *is* the architecture. Dependencies only ever point down this list —
nothing above a line knows anything below it exists:

```
hexagonal-architecture/
├── packages/
│   ├── shop-domain/           # entities: Order, Customer, Refund. Depends on nothing.
│   ├── shop-ports/            # the interfaces the application OWNS: OrderRepository,
│   │                          #   PaymentGateway, Mailer, FileStorage, JobQueue, AuditLog
│   ├── shop-core/             # the use cases, one request + one handler each, grouped
│   │                          #   by domain (orders, customers) — depends on pymediate,
│   │                          #   the entities, and the ports. Never on an adapter.
│   ├── shop-adapter-memory/   # every port on plain dicts — the test fakes that are
│   │                          #   also a real deployment
│   ├── shop-adapter-postgres/ # the persistence ports on psycopg. The only SQL in the repo.
│   ├── shop-adapter-neo4j/    # the same ports on a graph. The only Cypher in the repo.
│   └── shop-delivery/         # the doorways: Flask routes, Typer CLI, queue worker —
│                              #   each turns its input into a request and sends it
├── apps/                      # the composition roots — the ONLY code that knows which
│   ├── shop-memory/           #   adapters exist. ~40 lines each; diff any two and
│   ├── shop-postgres/         #   you'll find they differ only in wiring.py
│   └── shop-neo4j/
├── tests/
│   ├── core/                  # handlers with fakes: construct, call, assert. No patching.
│   ├── contracts/             # ONE suite every persistence adapter must pass
│   └── delivery/              # each doorway, driven by its framework's test tooling
├── Dockerfile                 # one file; a build ARG picks the composition root
└── compose.yaml               # profiles: memory | postgres | neo4j
```

Three rules produce that shape, and they're the whole trick:

1. **The core asks, it never fetches.** Every handler receives its collaborators
   through its constructor, typed as protocols from `shop-ports`. Nothing in
   `shop-core` imports a database driver, a web framework, or another domain's
   machinery — the refund handler adjusts store credit through the *customers port*,
   which is how the article's year-two circular import never forms.
2. **Adapters implement, they never decide.** `shop-adapter-postgres` knows SQL and
   nothing about refund policy. It could be deleted without touching a use case.
3. **Exactly one place chooses.** Each app in `apps/` is a composition root: it
   constructs real adapters, hands them to `shop_core.bootstrap.build_mediator`, and
   exposes entry points. Swapping databases is a different ~40-line package — not a
   conditional, not an env-var maze inside the core.

The seam that makes rule 1 cheap is the mediator. A doorway holds one line of
knowledge about any use case:

```python
result = mediator.send(ExportOrders(customer_id=customer_id))   # typed: ExportResult
```

and adding a use case to the whole system is one new file in `shop-core` plus one
line in `bootstrap.py`.

## One application, three databases

Each compose profile builds and runs a complete deployment on port 8000 — same API,
different machinery:

```bash
docker compose --profile memory up --build     # dicts; worker runs in-process
docker compose --profile postgres up --build   # Postgres + Redis + a worker container
docker compose --profile neo4j up --build      # Neo4j + Redis + a worker container
```

Talk to whichever is running:

```bash
curl -X POST localhost:8000/customers -H 'content-type: application/json' \
     -d '{"name": "Ada", "email": "ada@example.com"}'
# {"customer_id": "b39c...", "name": "Ada", "email": "ada@example.com", "store_credit_cents": 0}

curl -X POST localhost:8000/orders -H 'content-type: application/json' \
     -d '{"customer_id": "b39c...", "items": [{"sku": "widget", "quantity": 2, "unit_price_cents": 1999}]}'
# {"order_id": "56fa...", "status": "placed", ...}

curl -X POST localhost:8000/orders/56fa.../refund -H 'content-type: application/json' \
     -d '{"to_store_credit": true}'
# {"order_id": "56fa...", "amount_cents": 3998, "method": "store_credit", "reference": "store-credit/b39c..."}

curl -X POST localhost:8000/orders/export -H 'content-type: application/json' \
     -d '{"customer_id": "b39c..."}'
# {"status": "queued"}
```

That last call is the article's star ticket. The route answers `202` immediately; the
export happens wherever the worker doorway lives — a Redis-fed container in the
Postgres/Neo4j variants, a background thread in the memory one — and lands in the
worker's log:

```text
shop-postgres-worker-1  | INFO:shop.worker:export ready: file:///tmp/shop-exports/orders-b39c....csv (1 rows)
```

Same request object, different doorway. Nobody ported anything.

**The images really are isolated.** The `APP` build argument selects a composition
root, and `uv sync --package` installs only that package's dependency closure — so
this fails, by design:

```bash
docker compose --profile postgres run --rm --no-deps shop-postgres python -c "import neo4j"
# ModuleNotFoundError: No module named 'neo4j'
```

## Testing the adapters for real

`tests/contracts/` is one behavioral suite that every persistence adapter must pass.
Offline it runs against the in-memory adapter and skips the rest. Point it at live
services (the compose profiles publish their database ports) and the identical
assertions run against Postgres and Neo4j:

```bash
docker compose --profile postgres up -d
SHOP_TEST_DATABASE_URL=postgresql://shop:shop@localhost:5432/shop uv run pytest tests/contracts
```

```text
16 passed, 8 skipped
```

That suite is the executable meaning of "the adapters are interchangeable" — and it's
also why the core's own tests can use the memory adapter as their fakes with a clear
conscience: the fakes are held to the same contract as production.

The core tests themselves are the article's closing promise kept: construct a handler
with fakes, call it, assert on what it did —

```python
def test_refund_to_store_credit_credits_customer_not_gateway(orders, customers):
    order = place(orders, customers)
    gateway = RecordingPaymentGateway()
    handler = RefundOrderHandler(orders, customers, gateway, RecordingMailer())

    refund = handler(RefundOrder(order_id=order.order_id, to_store_credit=True))

    assert refund.method is RefundMethod.STORE_CREDIT
    assert gateway.refunds == []
```

No `@patch`, no app-context fixtures, no world-building `conftest.py`.

## The ideas, and where they come from

None of this structure is ours, and none of it is new — this example just makes it
cheap in Python:

- [*Nobody wants to touch that code*](https://pymediate.sina-al.uk/articles/nobody-wants-to-touch-that-code)
  — the story this example is the second half of: how the coupled version of this
  exact shop grows, and what the seam buys.
- Alistair Cockburn, [*Hexagonal Architecture*](https://alistair.cockburn.us/hexagonal-architecture/)
  — the original ports-and-adapters paper: the application in the middle, symmetric
  adapters plugging in from outside.
- Robert Martin, [*The Clean Architecture*](https://blog.cleancoders.com/2012-08-13-the-clean-architecture.html)
  — the dependency rule this tree follows: source dependencies point inward, toward
  the use cases.
- Herberto Graça, [*DDD, Hexagonal, Onion, Clean, CQRS — how I put it all together*](https://herbertograca.com/2017/11/16/explicit-architecture-01-ddd-hexagonal-onion-clean-cqrs-how-i-put-it-all-together/)
  — the best single map of how these overlapping schools relate.
- Harry Percival & Bob Gregory, [*Architecture Patterns with Python*](https://www.cosmicpython.com/)
  (free online) — repositories, service layers, and message buses in idiomatic Python;
  the contract-tests-for-fakes idea above is theirs.

## Where next

- [adapters-sync](../adapters-sync/) / [adapters-aio](../adapters-aio/) — the same
  framework-independence argument at a tenth of the size.
- [basic-sync](../basic-sync/) — the seam itself, in one file, if this example was
  your entry point.
- The docs: [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) ·
  [dependency injection](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [pipeline behaviors](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
