# Testing the Shop example

The test layout follows the same boundaries as the runtime code. A test stays in the package that
owns the behavior it verifies; the root suite is reserved for cross-package journeys and deployment
smoke checks.

## Test layers

| Layer | What is real | What it proves |
| --- | --- | --- |
| Domain unit | Entity, value object, or event | Invariants and immutable state transitions without a container or mediator. |
| Application unit | One handler and autospecced port protocols | Coordination, transaction scope, exact calls, responses, and failure behavior. |
| Application integration | Application container, PyMediate, and ephemeral adapters | Handler registration and a complete use case through `mediator.send()`. |
| Adapter unit | One concrete adapter and its local dependencies | Protocol mapping, lifecycle, serialization, idempotency, and settlement behavior. |
| Host integration | Real mediator behind Typer or FastAPI | Input translation, output safety, errors, and generated OpenAPI. |
| Acceptance | All local packages in one process | Outbox, relay, broker, consumer, second mediator dispatch, and observable effects. |
| Container integration | Real emulator or database through Testcontainers | SDK and server behavior that a process-local implementation cannot prove. |
| Deployment smoke | Already running Compose services | Health and one black-box API journey without reaching into containers. |

## Direct handler tests

Application unit tests do not use the mediator or Dependency Injector. They construct one handler
and use `unittest.mock.create_autospec()` against runtime-checkable port protocols:

```python
# Arrange
database = create_autospec(RefundOrderDbGateway, instance=True)
unit = create_autospec(UnitOfWork, instance=True)
handle = RefundOrderHandler(unit, database, journal, payments, mailer)

# Act
response = await handle(RefundOrderRequest(order_id=1, amount_pence=500))

# Assert
database.replace_order.assert_awaited_once()
assert response.refunded_pence == 500
```

This level should contain most use-case combinations. It identifies whether a failure belongs to a
handler rather than container registration, transport translation, or infrastructure.

Every test uses separate `# Arrange`, `# Act`, and `# Assert` sections. Handler instances are named
`handle`, leaving `Handler` for the class and avoiding an ambiguous variable beside mediator handler
registrations.

## Mediator-first tests

Application integration tests build the real feature containers and send requests through the
mediator without adding an HTTP or CLI adapter. These tests demonstrate the central promise of the
example: a use case is independently usable before a transport is chosen.

They enter the same resource lifecycle used by executables. Tests do not patch constructors or rely
on destructors to close SQLite, broker, storage, or SDK clients.

## Persistence concurrency

SQLite and PostgreSQL tests cover behavior that sequential happy-path tests miss:

- a unit of work belongs to one task and can be entered only once;
- child tasks cannot inherit access to a parent's transaction;
- standalone reads, relay claims, and inbox claims do not join another transaction;
- rollback in one unit does not roll back another task's work;
- generated identities remain unique under overlap;
- row locks prevent concurrent order or customer updates from losing state;
- stale lease owners cannot renew, release, or complete reclaimed work.

SQLite provides fast deterministic coverage. PostgreSQL Testcontainers tests verify the pool,
server-side locks, constraints, and transaction behavior against the production-shaped adapter.

## Messaging failure windows

Worker tests name the point at which a failure occurs. In particular, they distinguish:

- publish failed before broker acceptance;
- broker accepted but the relay did not mark the outbox row;
- mediator dispatch failed before inbox completion;
- inbox completion succeeded but broker completion failed;
- a processing or visibility lease expired and another worker reclaimed it;
- an idempotent external effect succeeded before message redelivery;
- a poison message reached the configured dead-letter threshold.

The complete local journey crosses the real serialization codec even though its queue is
process-local. Version-specific registry tests include an executable V1/V2 example so compatibility
rules are demonstrated rather than only described.

## Running checks

Run only this example from its directory:

```bash
uv run poe test
uv run poe check
```

`poe test` enforces 100% branch coverage for `shop.domain` and `shop.application`. The complete
suite still runs, but adapter and host lines are not included in that percentage.

Container integrations are opt-in:

```bash
RUN_TESTCONTAINERS=1 \
RUN_BROKER_TESTCONTAINERS=1 \
RUN_AZURE_SERVICE_BUS_TESTCONTAINERS=1 \
uv run pytest -m containers
```

Set only the corresponding variable when running the PostgreSQL and MinIO, LocalStack SQS, or
Service Bus emulator integration independently.

Smoke tests expect a deployment that is already running:

```bash
uv run poe compose:smoke --cloud aws
uv run poe compose:smoke --cloud azure
```

Compose model validation does not pull or build images:

```bash
uv run poe compose:config --cloud aws
uv run poe compose:config --cloud azure
```

Ruff checks formatting and lint rules. BasedPyright is the only static type checker configured for
this example and includes package source, scripts, root tests, and test configuration.
