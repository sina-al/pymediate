# Examples

These standalone projects form a learning path from the first typed request to a complete
multi-package application. Each project has its own dependencies, tests, editor settings,
and README.

Read `005-why-a-mediator` if you are deciding whether request handlers fit your application.
Start with `010-basic` to write one complete request-and-handler round trip.

## Run an example

From the repository root:

```bash
cd examples/005-why-a-mediator
uv sync
uv run pytest
```

```text
8 passed
```

Each example README shows its other commands and expected output. It also links to a GitHub
Codespace configured for that project.

## Choose a track

The unmarked directory is asynchronous and uses the top-level `pymediate` API. A directory
ending in `-sync` teaches the same topic with `pymediate.sync`. Read one track in numeric
order; use the other column when you need to compare the APIs.

The three-digit prefix is the curriculum position. Gaps allow new prerequisite topics to be
inserted without renaming every later example. Position `900` is reserved for the complete
application at the end.

## Curriculum

### Orientation and dispatch

| Position | Topic | Async | Sync | What you learn |
| --- | --- | --- | --- | --- |
| 005 | Why use a mediator? | [005-why-a-mediator](005-why-a-mediator/) | [005-why-a-mediator-sync](005-why-a-mediator-sync/) | Compare a multi-operation service with per-request handlers, including the trade-offs of adding a generic dispatch entry point. |
| 010 | Requests and responses | [010-basic](010-basic/) | [010-basic-sync](010-basic-sync/) | Define a typed request, register one handler, and call `send()`. This is the first implementation lesson. |
| 020 | Events | [020-events](020-events/) | [020-events-sync](020-events-sync/) | Publish one event to several handlers; async delivery is concurrent and sync delivery is sequential. |
| 030 | Streaming | [030-streaming](030-streaming/) | [030-streaming-sync](030-streaming-sync/) | Return typed chunks lazily with `stream()` and stop production when the consumer stops. |

### Composition and message design

| Position | Topic | Async | Sync | What you learn |
| --- | --- | --- | --- | --- |
| 040 | Pipeline behaviors | [040-pipeline-behaviors](040-pipeline-behaviors/) | [040-pipeline-behaviors-sync](040-pipeline-behaviors-sync/) | Select requests by type, order behaviors, and short-circuit the handler when appropriate. |
| 045 | Behaviors and decorators | [045-behaviors-vs-decorators](045-behaviors-vs-decorators/) | [045-behaviors-vs-decorators-sync](045-behaviors-vs-decorators-sync/) | Compare a method decorator with a behavior and decide whether a concern belongs on one handler or in mediator wiring. |
| 050 | Handler composition | [050-handler-composition](050-handler-composition/) | [050-handler-composition-sync](050-handler-composition-sync/) | Dispatch sub-requests from a handler, publish the result, and account for partial effects when concurrent work fails. |
| 060 | Request data | [060-messages](060-messages/) | [060-messages-sync](060-messages-sync/) | Use dataclass equality, hashing, validation, and `repr=False` deliberately in request types. |

### Application boundaries

| Position | Topic | Async | Sync | What you learn |
| --- | --- | --- | --- | --- |
| 065 | Validation | [065-validation](065-validation/) | [065-validation-sync](065-validation-sync/) | Validate transport shape at the edge and business rules in the core; compare direct and transformed mappings. |
| 070 | Error handling | [070-error-handling](070-error-handling/) | [070-error-handling-sync](070-error-handling-sync/) | Raise transport-independent errors in handlers and translate them separately for HTTP and CLI callers. |
| 075 | Identity and authorization | [075-authorization](075-authorization/) | [075-authorization-sync](075-authorization-sync/) | Extract identity at the edge, apply request-level authorization in behaviors, and check resource access after loading data. |
| 090 | Framework adapters | [090-adapters](090-adapters/) | [090-adapters-sync](090-adapters-sync/) | Serve one application through multiple web and CLI frameworks without importing them into the core. |

### Wiring and testing

| Position | Topic | Async | Sync | What you learn |
| --- | --- | --- | --- | --- |
| 100 | Dependency injection | [100-dependency-injection](100-dependency-injection/) | [100-dependency-injection-sync](100-dependency-injection-sync/) | Resolve handlers and behaviors from `dependency-injector` and compare its provider lifetimes. |
| 110 | Testing | [110-testing](110-testing/) | [110-testing-sync](110-testing-sync/) | Test handlers directly, replace an injected sender, and reserve a real mediator for wiring tests. |

### Projected data

| Position | Topic | Async | Sync | What you learn |
| --- | --- | --- | --- | --- |
| 130 | Command and query separation | [130-cqrs](130-cqrs/) | — | Separate write decisions from a projected read model, commit outbox records with writes, and account for eventual consistency. |

### Complete application

| Position | Topic | Example | What you learn |
| --- | --- | --- | --- |
| 900 | Hexagonal architecture | [900-hexagonal-architecture](900-hexagonal-architecture/) | Apply the earlier boundaries in a uv workspace with HTTP, CLI, and worker entry points plus replaceable local, AWS-compatible, and Azure-compatible infrastructure. |

## The examples contract

The release pipeline discovers every direct child matching `examples/*/pyproject.toml` and
runs it without project-specific workflow configuration. Each discovered project must meet
these requirements:

1. **It is a standalone uv project.** Its root contains `pyproject.toml`, `uv.lock`, and
   `README.md`. A multi-package example may define its own uv workspace, but no example may
   join the repository workspace or another example's workspace.
2. **It declares PyMediate directly with a loose lower bound.** A dependency such as
   `pymediate>=0.6.0` or `pymediate[di]>=0.6.0` lets the release runner replace the selected
   version without conflicting with an upper bound. Set the lower bound to the earliest known
   release whose API the example uses. This compatibility claim is maintainer-reviewed; the
   static contract check validates the requirement form, not every historical release.
3. **Its tests run after the default sync.** Pytest belongs to the `dev` dependency group,
   and `uv sync && uv run pytest` exits with status 0.
4. **It depends on the in-branch PyMediate source, and the release runner controls
   resolution.** Every example declares `pymediate = { path = "../..", editable = true }` in
   `[tool.uv.sources]`, so `uv sync` in a checkout runs the example against this source tree —
   including unreleased API on a feature branch. `[tool.uv.sources]` may otherwise only name
   packages inside the same example with `{ workspace = true }`, and the project contains no
   `[[tool.uv.index]]`. The runner strips the PyMediate source line from its temporary copy
   before applying a wheel or index pin, so releases are still verified against the built,
   published package rather than the checkout.
5. **The project is isolated.** It does not import another example or rely on another
   example's environment, files, or registered handlers.

Repository quality requirements extend this release contract. Every example also has a
three-digit curriculum name, a Codespaces configuration, standard Ruff and type-checker
settings, a clear README, and a matching entry in `pymediate.code-workspace`. The maintained
checklist is in [the `example` skill](../.claude/skills/example/SKILL.md). Run
`uv run poe examples:test --check-repository` to check its mechanical requirements.

## How CI and releases use the examples

The library test suite runs against the source tree. The examples run as downstream projects,
so they also check the built package and package-index installation path. Relevant pull
requests to `main` run both static checks and the complete gallery against a wheel.

| Stage | Runner mode | What it verifies |
| --- | --- | --- |
| Main pull request | both check targets, then `--wheel` | The release contract and repository structure are valid, and the reviewed source builds a wheel that every example can use. |
| Release pull request | `--wheel` | The reviewed source builds a wheel that every example can use before the release is merged. |
| Before TestPyPI | `--wheel` | The release-versioned artifact still works with dependencies resolved at release time. |
| After TestPyPI | `--version` with the TestPyPI index | The candidate can be resolved and installed from TestPyPI. |
| After PyPI | `--version` with the PyPI index | The published artifact users install passes the same examples before the GitHub Release is created. |

The runner copies each project to a temporary directory, applies the selected PyMediate pin,
and runs its tests. It never rewrites the checked-out example. In `--version` mode the pin is
an `explicit` uv index, so **only PyMediate** resolves from TestPyPI or PyPI while every other
dependency still resolves from real PyPI — a general index would let uv's first-index strategy
pull unrelated dependencies (pytest, click, …) off TestPyPI's stale placeholders and fail the
resolve. See [`OPERATIONS.md`](../OPERATIONS.md) and
[ADR 0007](../docs/adr/0007-examples-as-release-verification.md) for the release ordering and
design rationale.
