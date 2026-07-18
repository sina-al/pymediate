# Human-approved refunds with Restate and PyMediate

> Status: deferred implementation plan, reconciled with the flagship example on 18 July 2026.
>
> This file is intended to be sufficient for an agent with no prior session context. Read it in
> full before changing code. Delete it only after the implementation, documentation, and acceptance
> checks are complete.

## Objective

Replace the synchronous `RefundOrderHandler` with a durable refund process in which Restate owns
orchestration, retries, waiting, workflow-key deduplication, and the human-approval timeout;
PyMediate executes each business step; and the Shop database remains the authoritative source for
refund state and business audit history.

The result should demonstrate a meaningful use of PyMediate inside workflow steps without turning
Restate into the domain model, the business database, an event store, or a replacement for the
existing outbox and queue worker.

The intended high-level flow is:

```text
POST /orders/{order_id}/refunds
  -> Restate submission service
       -> durable mediator step: request refund and reserve refundable balance
       -> durable send: start RefundWorkflow keyed by refund_id
  -> 202 Accepted

RefundWorkflow
  -> durable mediator step: assess risk
  -> auto-approved
       -> durable mediator step: record system approval
  -> human review
       -> durable mediator step: mark pending approval
       -> wait for named durable promise or request-supplied timer
       -> decision handler persists the decision through the mediator, then resolves the promise
  -> durable mediator step: issue the idempotent payment refund
  -> durable mediator step: send the idempotent confirmation
```

The small Restate submission service is intentional. Calling the workflow's `/run/send` endpoint
directly would return `202` before `RequestRefund` has validated and persisted anything, creating a
period in which the advertised `Location` has no authoritative database record. The submission
service first runs the idempotent reservation step and then durably sends the workflow before it
returns. If implementation research reveals a simpler Restate-native primitive with the same
guarantee, document the evidence before changing this decision.

## Current baseline

The flagship example currently has 13 uv workspace distributions. Adding
`shop-adapter-restate` intentionally creates a fourteenth distribution. This is an explicit future
exception to the completed overhaul's instruction to retain 13 distributions; do not hide Restate
inside OpenAPI, bindings, or the application merely to preserve the old count.

Before implementation, read:

- the [flagship README](../README.md), especially its application rules and reliability boundary;
- [background processing](../docs/background-processing.md);
- [audit journal](../docs/audit-journal.md);
- [testing](../docs/testing.md);
- [third-party abstractions](../docs/third-party-abstractions.md);
- every affected package README.

Run the existing baseline before editing:

```bash
cd examples/900-hexagonal-architecture
uv sync --extra default --extra cli --extra openapi --extra worker
uv run poe check
uv run poe compose:config --cloud aws
uv run poe compose:config --cloud azure
```

At the time this plan was reconciled, the quality gate reported 361 passed, 7 opt-in skips, 100%
domain/application coverage, clean Ruff output, and zero BasedPyright errors or warnings. Test only
this flagship workspace. Do not run the repository's complete example suite.

There is no root `conftest.py`. Keep new fixtures beside the package whose resources they own.
Every test must contain one clean, spaced `# Arrange`, `# Act`, and `# Assert` section. A directly
constructed request handler is named `handle`, never `handler`.

### Current synchronous refund and why it is being replaced

The implementation is
[`shop.application.orders.refund_order`](../packages/shop-application/src/shop/application/orders/refund_order.py).
It currently:

1. opens a `UnitOfWork`;
2. loads and immutably refunds the `Order`;
3. commits the order change and `OrderRefundedEvent`;
4. calls the payment adapter after commit;
5. sends mail after payment.

Its tests deliberately prove that payment failure leaves the local order recorded as refunded and
that mail failure occurs after payment. A caller retry can issue the remote refund more than once.
There is no refund record, reservation, approval, retry state, or recovery path.

The new implementation must remove:

- `RefundOrderRequest`, `RefundOrderResponse`, and `RefundOrderHandler`;
- `shop.ports.orders.refund_order`;
- `OrdersContainer.refund_order`, `refund_payments`, and `refund_mailer`;
- `RefundOrderDbGateway` from `OrdersDbGateway`;
- the singular HTTP route `POST /orders/{order_id}/refund` and its DTOs;
- every stale test and documentation reference to the synchronous operation.

Keep `Order.refund()`. It remains the immutable domain operation that updates completed refund
totals when external settlement is known to have succeeded. Keep `OrderRefundedEvent`, but append it
only in the final successful settlement transaction so it continues to mean that the order refund
was committed, not merely requested.

## Boundaries that must remain distinct

The implementation has three durable records with different purposes:

- Restate's execution journal makes workflow actions deterministic across suspension and replay.
- `DomainEventJournal` records committed business facts for internal audit projections.
- Integration messages are versioned contracts for the existing outbox, relay, cloud queue, and
  worker.

Do not translate refund domain events into integration messages. Do not use the transactional
outbox to drive this workflow, and do not call `mediator.publish()` as a workflow mechanism. SQS,
Service Bus, the outbox relay, and the queue consumer remain unchanged for invoice, confirmation,
and export work.

Restate is an adapter. Nothing under `shop.domain`, `shop.application`, or an application-owned port
may import `restate`, HTTPX, FastAPI, or Restate contracts. Application requests and responses
remain frozen dataclasses. Restate's Pydantic contracts and serialization translations stay in
`shop-adapter-restate`.

## Domain model

Add these kind-based domain modules, matching the current package structure:

- `shop/domain/entities/refunds.py`;
- `shop/domain/errors/refunds.py`;
- `shop/domain/events/refunds.py`.

Add `AggregateType.REFUND` to `shop.domain.events.base.AggregateType`.

### Types

Use typed enums and immutable value objects rather than free-form status, recommendation, decision,
or source strings:

- `RefundStatus`;
- `RefundDecisionOutcome` (`APPROVED`, `REJECTED`);
- `RefundDecisionSource` (`SYSTEM`, `HUMAN`);
- `RefundRiskRecommendation` (`AUTO_APPROVE`, `REVIEW`);
- `RefundRiskAssessment` containing score, reasons, recommendation, and policy version;
- `RefundDecision` containing a UUID decision ID, outcome, source, reviewer, optional reason, and an
  aware UTC decision time;
- immutable `Refund`.

`Refund` contains at least:

- UUID `refund_id`;
- positive order and customer IDs;
- positive `amount_pence`;
- a stable request fingerprint derived from refund ID, order ID, and amount;
- status;
- aware UTC request and transition timestamps;
- optional risk assessment;
- optional decision;
- optional completion/payment reference;
- optional safe failure code and detail.

Validate coherent snapshots in `__post_init__`: UUIDs, identifiers, amount, UTC-aware timestamps,
nonblank reasons and reviewer names, risk-score bounds, and which optional fields are required or
forbidden in each status. Domain transitions return new values and never mutate an entity.

### State machine

```text
REQUESTED
├─ safe assessment  -> APPROVED            (system decision)
├─ risky assessment -> PENDING_APPROVAL
├─ cooperative workflow cancellation -> CANCELLED
└─ classified terminal pre-payment failure -> FAILED

PENDING_APPROVAL
├─ human approval  -> APPROVED
├─ human rejection -> REJECTED
├─ timer wins      -> EXPIRED
├─ cooperative workflow cancellation -> CANCELLED
└─ classified terminal pre-payment failure -> FAILED

APPROVED
├─ payment known successful + local commit -> COMPLETED
├─ cooperative cancellation before payment -> CANCELLED
└─ failure known to have made no payment -> FAILED
```

`REQUESTED`, `PENDING_APPROVAL`, and `APPROVED` reserve refundable balance. `REJECTED`, `EXPIRED`,
`CANCELLED`, and safely classified `FAILED` release it. `COMPLETED` is reflected in
`Order.refunded_pence` and therefore no longer needs a separate active reservation.

Never move an `APPROVED` refund to `FAILED` or release its reservation after an ambiguous payment
timeout. The provider may have completed the refund. Keep the refund approved, retry or pause the
workflow, and reconcile using the same idempotency key.

`COMPLETED` never becomes `FAILED` because confirmation mail failed. Notification recovery is an
operational concern after the money has been returned.

### Idempotency and conflict table

| Operation | Exact replay | Conflicting replay |
| --- | --- | --- |
| Request refund | Same refund UUID, order, and amount returns the existing refund. | Reusing the UUID for another order or amount raises `RefundIdempotencyConflictError`. |
| Risk assessment | Same policy version and result returns existing state. | A different result for an already assessed refund conflicts; policy changes require a new workflow contract version. |
| Human decision | Same decision UUID and identical outcome/reviewer/reason succeeds idempotently. | Same UUID with different data, a second decision, or a decision after rejection/expiry/completion conflicts. |
| Automatic approval | Repeating the same policy decision succeeds idempotently. | It cannot overwrite a human or terminal decision. |
| Payment completion | Repeating with the same refund UUID returns completed state. | Different payment data or completing a non-approved refund conflicts. |
| Confirmation | Same refund/outcome idempotency key produces one effect. | Reuse with different content is rejected by the adapter. |

The first committed human decision wins. Rejection requires a nonblank reason; approval may have an
optional reason. Human reviewers remain caller-supplied in this example and are not trustworthy
identity without authentication.

### Structured errors

Add explicit errors for at least:

- refund not found;
- refund UUID/input conflict;
- unavailable refundable balance;
- invalid refund transition;
- refund already decided;
- conflicting decision replay;
- decision too late;
- active refund preventing cancellation;
- invalid reviewer or reason;
- permanent payment rejection;
- invalid risk assessment snapshot.

Each error needs a stable code, title, safe detail, and structured context suitable for Problem
Details. Do not expose provider exceptions, payment secrets, or Restate journal data.

### Business audit facts

Add typed, versioned domain events rather than passing an event name and arbitrary payload around:

- `RefundRequestedEvent`;
- `RefundRiskAssessedEvent`;
- `RefundPendingApprovalEvent`;
- `RefundApprovedEvent`;
- `RefundRejectedEvent`;
- `RefundExpiredEvent`;
- `RefundCancelledEvent`;
- `RefundCompletedEvent`;
- `RefundFailedEvent`.

Append each fact in the same database transaction as its state change. When completion updates the
order, append both `RefundCompletedEvent` against the refund aggregate and the existing
`OrderRefundedEvent` against the order aggregate. Public projections continue to match by
`(event_type, schema_version)` and ignore unknown versions.

## Application use cases and ports

Create the feature-oriented package `shop.application.refunds` with `container.py` and one focused
module per operation. Create matching narrow runtime-checkable protocols under
`shop.ports.refunds`. Preserve the current rule that every request and response is explicitly named
`<Operation>Request` and `<Operation>Response`, and injected database attributes are `database` and
`_database`.

Required mediator operations:

- `RequestRefundRequest/Response`: lock the order, validate availability, insert an idempotent
  reservation, and append `RefundRequestedEvent`.
- `AssessRefundRiskRequest/Response`: call the risk port outside a transaction, then lock and persist
  the assessment and audit fact.
- `MarkRefundPendingApprovalRequest/Response`: persist the review-visible state.
- `ApproveRefundAutomaticallyRequest/Response`: record a typed system decision.
- `RecordRefundDecisionRequest/Response`: atomically accept the first human decision.
- `ExpireRefundRequest/Response`: expire only if still pending and return the effective persisted
  state so a racing decision can be reconciled.
- `CancelRefundRequest/Response`: idempotently release an active reservation during cooperative
  workflow cancellation, but never claim to undo a possibly completed payment.
- `IssueRefundRequest/Response`: perform idempotent external settlement and complete local state.
- `FailRefundRequest/Response`: record only a classified terminal failure known not to have made a
  payment.
- `SendRefundConfirmationRequest/Response`: send one outcome message using a stable idempotency key.
- `GetRefundRequest/Response`: query current authoritative status and allowlisted audit fields.
- `ListPendingRefundsRequest/Response`: return the reviewer work queue.

Every handler has comprehensive direct unit tests with autospecced protocols and no mediator. Cover
success, domain rejection, rollback, dependency failure, idempotent replay, conflicting replay,
exact events, exact responses, and remote-effect ordering.

Add `RefundsContainer`, including a feature-local `RefundsDbGateway` aggregate protocol, and mount it
under `ApplicationContainer`. Add only true application dependencies to `ApplicationContainer`:

- risk assessor;
- existing database, unit, clock, payments, mailer, and journal providers.

The Restate workflow client is host-facing and must not be an `ApplicationContainer` dependency.
It may have a small protocol in the Restate adapter for OpenAPI/CLI testing, but it is not an
application outbound port.

### Clock and risk policy

Add a narrow `RefundClock.now() -> datetime` port requiring aware UTC output. Extend
`shop.adapters.common.clock.SystemClock`, which already owns the shared clock implementation.

The threshold risk policy is stateless, so it belongs in `shop-adapter-common`, not
`shop-adapter-ephemeral`. Add a `ThresholdRefundRiskAssessor` with an explicit, documented policy:

- add 50 points when the refund is at least £20;
- add 50 points when it is at least 50% of currently refundable balance;
- a score of 50 or more requires review.

Use integer pence and integer ratios/basis points rather than floating-point money comparisons.
Make thresholds validated provider arguments. Persist the policy version, score, reasons, and
recommendation before branching so replay does not recalculate history with new configuration.

## Transaction and settlement algorithms

No database transaction may remain open while waiting for risk assessment, payment, mail, a human,
or a Restate timer.

### Requesting and reserving

`RequestRefundHandler` must, in one explicit unit of work:

1. lock the order;
2. check an existing refund with the same UUID and apply the idempotency table;
3. calculate available balance as:

   ```text
   order.total_pence - order.refunded_pence - active refund reservations
   ```

4. validate the requested amount;
5. insert `REQUESTED` refund state;
6. append `RefundRequestedEvent`.

Both refund reservation and order cancellation lock the same order first. PostgreSQL then queries
or locks related refunds while holding that row lock; SQLite relies on its serialized transaction.
This common lock order prevents cancellation from racing a new reservation and avoids deadlocks.

Update `CancelOrderHandler` and its narrow database contract to reject cancellation while an active
refund reservation exists. Keep this cross-record policy in the application handler, not
`Order.cancel()`.

### Issuing payment

`IssueRefundHandler` uses this ordering:

1. read/verify that the refund is approved without holding a transaction across the remote call;
2. call the payment adapter with `refund_id` as the idempotency key;
3. open a new unit of work and lock refund then order using the documented common lock order;
4. if already completed, return the persisted response;
5. apply `Order.refund(amount_pence)`;
6. persist order and completed refund;
7. append `RefundCompletedEvent` and `OrderRefundedEvent` atomically.

If payment succeeds and the process stops before the database commit, Restate re-enters the named
step. The payment provider receives the same key and returns the same effect; the local transaction
then completes. This is at-least-once execution with idempotent effects, not a claim that Restate
magically makes an arbitrary payment API exactly once.

The current payment implementation also serves create-order compensation. Preserve compatibility
with a method shaped like:

```python
async def refund(
    order_id: int,
    amount_pence: int,
    *,
    idempotency_key: str | None = None,
) -> None: ...
```

The workflow refund port requires a key; the create-order compensation port may omit it. The
ephemeral adapter suppresses exact duplicate keyed refunds and rejects reuse of a key with different
parameters. Process-memory suppression demonstrates retry behavior only within one adapter process;
it does not survive restart. Real payment safety requires provider-native idempotency or a durable
effect ledger.

### Confirmation and failure

Send confirmation only after a persisted terminal business outcome. Use a stable key such as
`refund:{refund_id}:{outcome}:confirmation`. Exact retries produce one message; conflicting key use
fails loudly.

Classify failures before changing business state:

- known domain rejection: terminal;
- transient database/payment/mail failure: retry;
- explicit permanent payment decline known to have made no payment: terminal and eligible for
  `FAILED` plus reservation release;
- payment timeout or unknown outcome: ambiguous, retain reservation and retry/reconcile;
- mail failure after completion: retry notification, never fail the completed refund.

If failure recording itself fails, let that durable step retry. Do not swallow the original
terminal classification or broadly catch SDK exceptions.

## Persistence changes

Extend the already split persistence adapters rather than creating a refund repository package:

- SQLite schema: `shop-adapter-ephemeral/.../sqlite_schema.py`;
- SQLite gateway: `shop-adapter-ephemeral/.../sqlite.py`;
- PostgreSQL schema: `shop-adapter-postgres/.../schema.py`;
- PostgreSQL gateway: `shop-adapter-postgres/.../gateway.py`.

Retain package-level exports and the current one concrete gateway per database adapter. Those
gateways implement the new narrow protocols structurally.

The refund table needs at least:

- UUID/text primary key and request fingerprint;
- order/customer IDs and amount;
- status and timestamps;
- risk score, reasons, recommendation, and policy version;
- decision UUID, source, outcome, reviewer, reason, and time;
- payment reference;
- safe failure code/detail.

Use native UUID/JSONB in PostgreSQL and validated text/JSON in SQLite. Add an order/status index,
pending-review index, and uniqueness for decision IDs. Fresh-test schema creation remains
idempotent; adding a production migration framework is out of scope.

Preserve the current persistence guarantees:

- PostgreSQL uses a pooled connection bound to the exact transaction-owning task and `FOR UPDATE`
  for mutable records;
- SQLite uses a shared aiosqlite connection with serialized access and exact-task transaction
  ownership;
- units of work remain one-shot and reject nesting, concurrent/sequential reuse, and child-task
  access;
- no relay, inbox, or standalone read silently joins another task's transaction.

## Restate adapter

Add `packages/shop-adapter-restate` with namespace `shop.adapters.restate`, a complete README, its
own focused tests, and these responsibilities:

- adapter-owned Pydantic submission, workflow, decision, step-result, and error contracts;
- `RefundSubmissionService`;
- `RefundWorkflow`;
- HTTPX `RestateRefundWorkflowGateway` for public hosts;
- a small host DI container;
- a factory that binds the services to a Restate ASGI application;
- settings and lifecycle for the HTTP ingress client.

It is a dual-role technology adapter:

- Restate invokes its mounted ASGI service, making that side a primary adapter into PyMediate;
- OpenAPI and CLI call its ingress gateway, making that side a secondary technology client for
  those hosts.

This is cohesive around one workflow engine, but the README must explain both directions and state
that the application core has no Restate dependency.

Use the implementation-time verified compatible pair:

- `restate_sdk[serde]==1.0.2` at runtime;
- `restate_sdk[harness]==1.0.2` only in test dependencies;
- Restate Server `1.7.2`, pinned by tag and image digest in `.env.images`.

The Python SDK 1.0 compatibility matrix supports Restate 1.7. Recheck the official matrix and image
digest immediately before implementation because these are external release facts.

Do not use experimental protocol-v7 `ctx.signal()` for approval. Use a named workflow durable
promise, which is the established primitive for human-in-the-loop workflow signalling.

### Serialization boundary

Every mediator dispatch is non-deterministic from Restate's perspective and must be inside a named
`ctx.run_typed` action. Application responses are dataclasses; do not make them Pydantic merely for
Restate. Convert them inside the adapter to explicit Pydantic step-result contracts and supply the
appropriate type hint/serde.

Keep the adapter helper small and visible. It may remove repetitive serialization, but it must not
hide durable step names, retry policy, or which mediator request is being sent.

Step names and order are persisted workflow history. Give them stable versioned names such as:

```text
request-refund-v1
assess-refund-risk-v1
record-system-approval-v1
mark-pending-approval-v1
record-human-decision-v1
expire-refund-v1
issue-refund-v1
send-refund-confirmation-v1
cancel-refund-v1
fail-refund-v1
```

Do not rename, reorder, insert ahead of, or change the serialization contract of actions used by
live workflows without a Restate deployment/versioning plan.

### Submission service

The public gateway invokes `RefundSubmissionService.submit` request-response and supplies the
refund UUID as both an input field and Restate invocation idempotency key. The handler:

1. runs `RequestRefundRequest` as `request-refund-v1`;
2. converts allowlisted `DomainError` values into a typed rejected submission result rather than
   retrying permanent business input;
3. durably sends `RefundWorkflow.run` using `refund_id` as the workflow key;
4. returns an accepted result only after that send is journalled.

The gateway maps typed rejected results back to the existing concrete domain errors so OpenAPI's
individual Problem Details handlers and CLI's domain-error presentation remain consistent. Do not
pass arbitrary exception objects or unfiltered contexts through Restate.

Restate invocation-key retention is not the business idempotency boundary. The database fingerprint
still detects same UUID/different request after Restate's idempotency retention expires.

### Workflow algorithm

The workflow input includes all replay-sensitive values:

- refund UUID and expected workflow key;
- order and amount fingerprint/version;
- approval timeout seconds;
- risk policy version;
- workflow contract version.

Do not reread a mutable timeout or policy from environment variables after execution begins.

The main handler:

1. verifies `ctx.key()` matches the request refund UUID;
2. dispatches and persists risk assessment;
3. for auto-approval, dispatches the typed system decision;
4. for review, marks the refund pending and races:

   ```python
   approval = ctx.promise("approval-v1", type_hint=RefundDecisionContract).value()
   timeout = ctx.sleep(timedelta(seconds=request.approval_timeout_seconds))

   match await restate.select(approval=approval, timeout=timeout):
       case ["approval", decision]:
           ...
       case ["timeout", _]:
           ...
   ```

5. reconciles the persisted winning state;
6. if approved, issues payment;
7. sends the appropriate idempotent confirmation;
8. returns an explicit workflow result while the database remains authoritative.

Rejection is normal decision data. Do not reject the promise to represent a business rejection;
promise rejection produces a terminal workflow error.

### Decision-versus-timeout race

The shared `decide` handler must persist before signalling:

1. execute `RecordRefundDecisionRequest` through `ctx.run_typed`;
2. let row locking and the refund state transition decide whether it won;
3. only after persistence succeeds, resolve `approval-v1` with the typed decision;
4. return request-response to the gateway so a known duplicate/late decision can become HTTP 409.

`ExpireRefundRequest` is atomic: expire only if the row is still pending, otherwise return the
effective approved/rejected state. If the timer future wins while a decision has committed but its
promise has not yet resolved, the workflow observes that persisted decision and follows it instead
of incorrectly expiring the refund.

Add an early harness spike before finalizing the public 409 promise. Official documentation does
not define every already-resolved-promise response. Prove exact duplicate, conflicting duplicate,
and post-timeout decision behavior against the pinned SDK/server. Persisted database state is the
ultimate answer even if an ingress response races it.

### Retries, terminal errors, cancellation, and kill

Restate retries ordinary failures. Convert known permanent `DomainError` values to `TerminalError`
inside the narrow mediator step wrapper; allow infrastructure failures to retry. Never put a broad
`except Exception` around Restate context operations because it catches SDK control-flow errors.

Configure invocation and important run-step retry policies explicitly. Current documentation has
historically described defaults differently across SDK and server pages; do not make safety depend
on an implicit attempt count. Use current `InvocationRetryPolicy`, `RunOptions`, and
`RetryableError(retry_after=...)` APIs verified against SDK 1.0.2.

Cooperative invocation cancellation is surfaced at an awaited Restate action as a terminal error.
After reservation, narrowly handle supported cancellation metadata and dispatch the idempotent
`CancelRefundRequest` durable step before re-raising. Do not collapse cancellation into `FAILED`.

Administrative kill does not run compensation. Document it as a last resort. Provide and test an
operator-mediated repair path that inspects payment state before dispatching a safe cancellation or
failure transition; never automatically release an ambiguous approved reservation. If SDK 1.0.2
does not expose cancellation classification reliably, record that limitation and prefer explicit
workflow cancellation/repair handlers over a broad terminal-error catch.

## OpenAPI contract

Add `shop.openapi.routes.refunds`, register it with the router/wiring modules, and keep the existing
small app factory, Pydantic DTO layer, and individual error handlers.

Public routes:

- `POST /orders/{order_id}/refunds`
  - body contains positive `amount_pence`;
  - requires UUID `Idempotency-Key` as refund ID;
  - invokes the Restate submission service;
  - returns `202 Accepted`, `Location: /refunds/{refund_id}`, refund ID, and submitted status only
    after the reservation and durable workflow send succeed.
- `GET /refunds/{refund_id}` returns persisted status, amount, risk recommendation, reviewer
  decision, timestamps, and safe failure information without exposing the domain entity.
- `GET /refunds?status=pending-approval` returns the review queue.
- `POST /refunds/{refund_id}/decision`
  - requires a UUID decision `Idempotency-Key`;
  - accepts approve/reject, reviewer, and optional reason;
  - requires a reason for rejection;
  - calls the Restate decision handler request-response;
  - returns `202` for an accepted or exact duplicate decision and `409` for a proven conflict.

Add individual Problem Details translations for all new domain errors. Add a safe `503` problem for
Restate ingress unavailability. Preserve the logged fallback for an unregistered `DomainError`.
OpenAPI descriptions must make reviewer spoofing and asynchronous workflow status clear.

`/restate/v1` is the service endpoint called by Restate, not the public workflow ingress. Mount it
using the Restate ASGI factory inside FastAPI as officially supported.

## CLI contract

Add a focused `shop.cli.commands.refunds` group:

```text
shop refunds request --order 1 --amount 2500 [--idempotency-key UUID]
shop refunds pending
shop refunds show REFUND_ID
shop refunds approve REFUND_ID --reviewer NAME [--reason TEXT] [--idempotency-key UUID]
shop refunds reject REFUND_ID --reviewer NAME --reason TEXT [--idempotency-key UUID]
```

Generate and visibly print refund/decision UUIDs when omitted. Preserve `get_context()`, Rich cards
and tables, typed application responses, and one `asyncio.run()` lifecycle per command. Workflow
gateway resources must be initialized, used, and closed in the same event loop.

The default profile's SQLite database is process-local. A standalone CLI does not share state with
a separately running OpenAPI/Restate service. Demonstrate cross-command human review from the AWS
or Azure administration container backed by PostgreSQL, or through a single-process/harness test.
Do not imply that independent default-profile commands form one workflow.

## Composition and dependency isolation

Current YAML supports only `application`, `relay`, and `consumer`, and `create_wiring()` eagerly
imports every declared provider. If shared manifests name a Restate implementation, a worker image
without the SDK fails while loading an unused provider. Resolve this before adding Restate to the
manifests.

Recommended composition change:

- add `risk` to `ApplicationContainer` and the application provider bindings;
- add optional `openapi` and `cli` host roles, each selecting `refund_workflows` and any host-owned
  lifecycle resources;
- activate `application + openapi` in FastAPI;
- activate `application + cli` for workflow CLI commands;
- preserve `relay` without an application container and `application + consumer` for the worker;
- make implementation import, environment resolution, and provider construction lazy for the
  provider closure reachable from selected roles;
- still validate provider names, `$ref` existence, resource references, and cycles from the entire
  manifest before execution;
- cache resolved providers so resources shared across selected roles remain deduplicated.

Add tests proving:

- a worker can load a manifest whose unselected host role references an uninstalled Restate module;
- selecting that host gives a precise dotted-import diagnostic;
- missing host-only Restate environment variables do not affect relay/consumer startup;
- host role resources initialize and shut down once;
- startup failure cleans only resources already initialized for the selected roles;
- runtime validation and `configuration.schema.json` remain synchronized.

Do not add Restate to `shop-bindings`' mandatory dependencies or any worker extra. OpenAPI and CLI
host extras install `shop-adapter-restate`; worker images contain neither the Restate SDK, HTTPX
client, FastAPI, nor Typer unless that host owns them.

Use small host-owned Dependency Injector containers rather than constructing gateways in routes or
commands. Keep YAML provider terminology (`providers`, `$ref`, `impl`) and do not reintroduce
profiles of manually wired Python objects.

## Configuration

Add validated, adapter-owned settings for:

- `SHOP_RESTATE_INGRESS_URL` (the host gateway calls Restate here, normally
  `http://restate:8080` in Compose);
- `SHOP_RESTATE_IDENTITY_PUBLIC_KEY` for validating calls to the mounted service endpoint;
- `SHOP_REFUND_APPROVAL_TIMEOUT_SECONDS` (default 300, copied into workflow input);
- risk thresholds and a risk policy version;
- explicit retry-policy values where configuration is warranted.

Keep the configured ingress address distinct from Restate's registered service deployment URL,
`http://shop-openapi:8000/restate/v1`.

Extend all three provider manifests and `configuration.schema.json` with descriptions, required
properties, strict unknown-property rejection, role-specific required provider sets, and editor
squiggles. Environment mappings remain one-line YAML objects. Any `$ref` remains a one-line object.

The selected host should require only its own environment variables. This is another acceptance
test for lazy role resolution.

## Compose, images, and registration

Restate belongs in shared `compose.yaml` because AWS and Azure overlays both use it. The base file is
not independently deployed today; cloud overlays provide the host images and shared PostgreSQL
state.

Add:

- `RESTATE_IMAGE` and, if used, `RESTATE_CLI_IMAGE` in `.env.images`, each pinned by version and digest;
- Restate Server 1.7.2 with a stable node name and persistent named volume;
- health checks;
- localhost-only ingress `8080` and UI/admin `9070` bindings;
- a one-shot registration service or task that waits for Restate and OpenAPI, then runs:

  ```text
  restate deployments register \
    --use-http1.1 \
    http://shop-openapi:8000/restate/v1
  ```

- dependency ordering that does not create an OpenAPI/registration cycle;
- Poe tasks for registration, status, logs, UI guidance, and approval/rejection/timeout demos;
- existing `env --cloud aws|azure` integration rather than another combinatorial profile matrix.

Uvicorn is HTTP/1.1, so registration must use the HTTP/1.1 flag. Mounting an ASGI app is not enough;
Restate must discover/register the endpoint.

The OpenAPI and administration images include their selected infrastructure plus Restate client
code. Worker images remain host-specific and minimal. Validate merged Compose models without
pulling or building images unless the user separately authorizes it.

### Local durability limitation

Restate's persistent journal does not make the default `:memory:` SQLite database, ephemeral
payment ledger, or ConsoleMailer survive an API restart. A Restate restart while the same API
process remains alive demonstrates durable waiting. Full service-restart recovery and
cross-process review require PostgreSQL plus genuinely durable/idempotent external effects.

State claims in docs and tests must distinguish:

- orchestration recovery;
- authoritative database recovery;
- external-effect idempotency recovery.

Do not claim end-to-end restart safety when only the Restate journal survives.

## Security and operations

The mounted Restate service endpoint must not be treated as a normal public application endpoint.
The local mount is a teaching convenience. Production deployments should restrict it so only the
intended Restate instance can reach it and enable Restate request-identity verification through
`restate.app(..., identity_keys=[...])`.

Protect Restate ingress and UI/admin ports. Do not forward credentials or unnecessary sensitive
headers: invocation headers and inputs may be retained in Restate history. Caller-supplied reviewer
identity is explicitly not authentication or authorization.

Feed Restate server OTLP traces into the existing OpenTelemetry Collector and preserve W3C trace
context. Do not add another telemetry abstraction. Restate metrics are exposed on its internal
monitoring endpoint and should not be publicly mapped. Document how `restate.invocation.id`, refund
ID, application request type, and existing service names let an operator correlate work.

Long-running workflows stay attached to the deployment revision on which they began. Keep old
service revisions reachable until their workflows drain. Reordering durable actions can produce
non-determinism. Document registration, drain, cancellation, pause/resume, and last-resort kill
behavior in the operational guide.

## Testing plan

### Domain

Cover every valid transition and every rejected transition, immutable results, required fields,
reservation-state classification, decision idempotency/conflicts, aware timestamps, risk value
objects, structured errors, and exact event payloads.

### Direct application tests

Create `packages/shop-application/tests/unit/refunds/test_*.py`, one comprehensive suite per use
case. Use autospecced protocols and call `handle(request)` directly without a mediator. Verify exact
transaction boundaries, rollback, events, responses, dependency failures, payment ordering,
ambiguous outcomes, and idempotent replay.

### Mediator integration

Exercise every refund request through the real `ApplicationContainer.mediator()` without Restate
or an inbound adapter. Move refund scenarios out of order integration tests. Cover auto approval,
human transitions, payment completion, queries, cancellation conflict, and customer closure after
partial/full settlement.

### Persistence and secondary adapters

SQLite and opt-in PostgreSQL tests cover:

- same/different UUID replay;
- overlapping reservations;
- cancellation versus reservation;
- decision versus expiry;
- row-lock ordering and rollback isolation;
- payment-success/database-failure replay;
- exact uniqueness/index behavior;
- independent reads and task-owned units of work.

Ephemeral payment/mail tests prove exact duplicate suppression and conflicting key rejection while
stating their process-memory limitation. Common-adapter tests cover policy thresholds and boundary
values.

### Restate adapter

Unit-test the HTTPX gateway with a mock transport: URLs, headers, Pydantic payloads, accepted
responses, typed domain rejection, previously accepted workflows, unavailable ingress, decision
conflicts, attach/output, and client closure.

Use the official opt-in Python harness only for behavior it actually supports:

```python
with restate.test_harness(app) as harness:
    ingress = harness.ingress_client()
```

Gate container-backed tests with `RUN_RESTATE_TESTCONTAINERS=1`. Use short request-supplied timeouts.
Do not assume the harness provides time travel, restart, or fault injection. Inspect the pinned
1.0.2 harness first; use explicit Testcontainers/Compose orchestration for real server or endpoint
restart tests if necessary.

Required Restate scenarios:

- accepted submission and durable workflow send;
- same-key/same-input duplicate and same-key/different-input conflict;
- auto approval, human approval, rejection, and timeout;
- two concurrent reviewers;
- decision immediately before and after timeout;
- decision persisted before promise resolution;
- duplicate and conflicting promise resolution behavior;
- transient mediator-step retry;
- terminal domain error translation without catching SDK internals;
- payment success followed by local commit failure;
- ambiguous payment outcome;
- notification retry after completed refund;
- cooperative cancellation compensation;
- explicit documentation/test limits for administrative kill;
- Restate restart/durable-promise recovery with database/effect limitations stated accurately.

### Hosts, composition, and deployment

OpenAPI tests cover 202/Location, status, pending list, decisions, UUID validation, rejection reason,
individual 404/409/422 problems, Restate 503, mounted endpoint, Swagger contracts, and the logged
domain safety fallback.

CLI tests cover all commands, generated/displayed IDs, Rich output, domain failures, ingress
failures, and same-event-loop resource shutdown.

Bindings tests cover schema/runtime parity, lazy role imports, missing role-specific environment,
cycles, startup cleanup, shared resource deduplication, and profile extras. Compose tests cover
registration, health/dependency shape, pinned images, persistent volume/node identity, minimal host
images, and both merged cloud configurations.

The configured 100% gate continues to cover `shop.domain` and `shop.application`. The Restate
adapter receives comprehensive focused tests but is not silently added to that percentage unless
the coverage configuration and rationale are changed explicitly.

## Documentation work

Update, without overstating guarantees:

- the main README's domain map, component flow, package table, reliability boundary, executable
  adapters, profiles, commands, testing, and non-goals;
- `docs/audit-journal.md`, especially the old claim that the order fact commits before payment;
- `docs/testing.md`, whose examples currently use `RefundOrderHandler`;
- `docs/background-processing.md` only to contrast Restate orchestration from outbox delivery;
- a new detailed `docs/refund-workflow.md` covering the state machine, journals, idempotency,
  timeout race, retries, cancellation/kill, security, versioning, and local limitations;
- READMEs for domain, ports, application, common, ephemeral, PostgreSQL, bindings, OpenAPI, CLI,
  worker where affected, and the new Restate package;
- the example gallery and workspace/package map;
- devcontainer dependencies, VS Code analysis, uv sources/extras/lockfile, Docker context, and release
  runner expectations.

Keep the Restate path optional advanced reading. The five-minute `poe demo` currently has no refund
and should remain Restate-free unless a separate opt-in workflow demo is deliberately added. Do not
make a workflow engine a prerequisite for understanding a small handler.

## Ordered migration

Complete one phase before starting the next:

1. Run and record the baseline. Verify SDK/server compatibility and image digests from official
   sources.
2. Freeze the state machine, idempotency table, submission contract, timeout arbitration, and
   failure classification in tests and docs.
3. Add refund domain objects, errors, events, ports, application requests/handlers, and direct unit
   tests while the old handler still exists.
4. Add SQLite/PostgreSQL persistence and concurrency coverage.
5. Add common risk policy, clock capability, and idempotent ephemeral payment/mail behavior.
6. Add `RefundsContainer`, application bindings, and mediator-first integration tests.
7. Update cancellation reservation checks. Only now remove the old synchronous handler and ports.
8. Refactor wiring to lazy role provider resolution and add host roles, schema, lifecycle, and
   isolation tests before any manifest references Restate.
9. Add `shop-adapter-restate`, first proving gateway and promise/timeout semantics with the pinned
   harness.
10. Add submission service, workflow, decision handler, retry/cancellation behavior, and complete
    Restate tests.
11. Integrate OpenAPI and CLI host containers, routes, DTOs, Problem Details, commands, and
    lifecycle tests.
12. Add Compose server, registration, security, observability, image pins, Poe tasks, and merged
    model validation.
13. Update every README/guide/gallery entry and remove stale synchronous-refund claims.
14. Run all acceptance gates, remove generated caches, and delete this todo only when nothing
    remains deferred.

## Exact stale-reference audit

Before declaring completion, inspect every result from:

```bash
rg -n "RefundOrder|refund_order|refund_payments|refund_mailer|/refund\b" .
```

Expected intentional matches should be none outside release history or an explicitly labelled
migration note. Pay particular attention to:

- `packages/shop-application/tests/unit/orders/test_refund_order.py`;
- application integration order/customer tests;
- `packages/shop-adapter-openapi/tests/integration/test_openapi.py`;
- `tests/acceptance/test_article_workflow.py`;
- typing assertions in `tests/typing/mediator_types.py`;
- all profile/dependency/package-metadata tests;
- every package README and the main README;
- audit/testing guides and Swagger examples.

## Acceptance checklist

- The application/domain/ports import no Restate or HTTP framework.
- `shop-adapter-restate` is the documented fourteenth distribution.
- No old synchronous refund handler or route remains.
- Every business step is directly testable and mediator-testable without Restate.
- The database, not Restate state, answers refund and pending-review queries.
- Request and decision idempotency distinguish exact from conflicting replay.
- Active reservations serialize with cancellation and concurrent refunds.
- Payment is never called inside an open database transaction.
- Payment and mail use stable effect idempotency keys.
- Ambiguous payment outcomes never release the reservation or claim failure.
- `OrderRefundedEvent` is appended only with successful local completion.
- The decision handler persists before resolving the durable promise.
- Timeout/decision races reconcile persisted state.
- Known domain errors are terminal; transient infrastructure failures retry.
- SDK internal exceptions are never broadly caught.
- Cooperative cancellation is compensated; administrative kill limitations are explicit.
- Workflow input captures timeout and policy version; durable action names are stable/versioned.
- Restate request identity, private routing, ingress/UI protection, and sensitive-journal data are
  documented.
- OpenAPI/CLI roles own Restate lifecycle; workers do not import or install Restate.
- Shared manifests resolve only providers reachable from selected roles.
- Default SQLite/process-memory restart limits are explicit.
- Restate service registration is automated and uses HTTP/1.1.
- Every image is pinned by tag and digest.
- Package-local tests retain Arrange/Act/Assert and `handle` conventions.
- `uv run poe check` passes with 100% configured coverage and clean Ruff/BasedPyright.
- AWS and Azure merged Compose models validate without pulling/building images.
- Opt-in Restate/PostgreSQL tests pass when Docker is available.
- All local Markdown links and documented commands are valid.
- Generated caches are absent.

## Non-goals

- Restate does not replace the database, domain journal, integration messages, or PyMediate.
- This does not implement authentication, authorization, a real reviewer identity provider, or a
  reviewer web UI.
- This does not add production payment/mail providers or claim process-memory idempotency survives
  restarts.
- This does not add a database migration framework, infrastructure-as-code, or a highly available
  Restate cluster.
- This does not route invoices, confirmations, or exports through Restate.
- This does not make the ordinary five-minute demo depend on Docker or Restate.
- This does not present the entire flagship structure as the default for smaller applications.
- No commit, push, Docker pull, or unrelated repository change is implied by this plan.

## Official references

- [Restate Server changelog](https://docs.restate.dev/changelog/server)
- [Python SDK repository, releases, and compatibility matrix](https://github.com/restatedev/sdk-python)
- [Python services and workflows](https://docs.restate.dev/develop/python/services)
- [External events and durable promises](https://docs.restate.dev/develop/python/external-events)
- [Durable steps](https://docs.restate.dev/develop/python/durable-steps)
- [Durable timers](https://docs.restate.dev/develop/python/durable-timers)
- [Concurrent durable tasks](https://docs.restate.dev/develop/python/concurrent-tasks)
- [Python serialization](https://docs.restate.dev/develop/python/serialization)
- [Python error handling](https://docs.restate.dev/develop/python/error-handling)
- [HTTP invocation API](https://docs.restate.dev/services/invocation/http)
- [Python serving and FastAPI mounting](https://docs.restate.dev/develop/python/serving)
- [Python testing harness](https://docs.restate.dev/develop/python/testing)
- [Database integration guidance](https://docs.restate.dev/guides/databases)
- [Saga and compensation guidance](https://docs.restate.dev/guides/sagas)
- [Service security and request identity](https://docs.restate.dev/services/security)
- [Invocation management, cancellation, and kill](https://docs.restate.dev/services/invocation/managing-invocations)
- [Service deployment versioning](https://docs.restate.dev/services/versioning)
- [Docker deployment](https://docs.restate.dev/server/deploy/docker)
- [Restate tracing](https://docs.restate.dev/server/monitoring/tracing)
- [Restate metrics](https://docs.restate.dev/server/monitoring/metrics)
