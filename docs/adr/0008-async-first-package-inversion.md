# ADR 0008: Async-first package inversion

**Status:** Proposed
**Date:** 2026-07-11
**Author:** Claude
**Reviewers:** @sina-al

## Context

PyMediate positions itself as a mediator library for *modern* Python — 3.12+, fully typed,
riding alongside the FastAPI/Starlette family. But the package namespace says the opposite:
the top-level `pymediate` package is the **synchronous** API, and async — the default mode
of the ecosystem the library targets — lives in the `pymediate.aio` annex:

```python
# today: async is the annex
from pymediate import Request, Services            # shared
from pymediate.aio import RequestHandler, Mediator  # async

# sync gets the prestige namespace
from pymediate import RequestHandler, Mediator
```

Issue #45 (maintainer interview, 2026-07-10) locked the decision to invert this: the
top-level package becomes the async API, sync moves to a new `pymediate.sync` subpackage,
and `pymediate.aio` is deleted outright. ZeroVer sanctions the break (major version zero;
see "Versioning" in `CLAUDE.md`), and the next release is already a breaking minor
(`0.5.0`) because the deprecated `Handler` alias was removed on main after ADR 0006.

One naming note: issue #45's code samples predate ADR 0006 landing and say `Handler`; the
class is `RequestHandler` everywhere below.

Issue #44 (one-line async imports: make `pymediate.aio` re-export the shared API) is
superseded by this design — its goal is absorbed, rotated, by the full-mirror decision for
`pymediate.sync`, and its superset+identity parity-test idea transfers with it.

## Proposed Solution(s)

### Option A: Hard swap — `pymediate` is async, `pymediate.sync` is the mirror, `aio` deleted (RECOMMENDED, locked by maintainer)

```python
# after
from pymediate import Request, RequestHandler, Mediator, Services      # async
from pymediate.sync import Request, RequestHandler, Mediator, Services  # sync
import pymediate.aio  # ModuleNotFoundError
```

Module re-homing (shared names keep exactly one definition):

| Module | Before | After |
|---|---|---|
| `pymediate/request.py`, `service.py`, `errors.py` | shared definitions | unchanged |
| `pymediate/handler.py`, `mediator.py`, `pipeline.py` | sync classes | **async** classes (moved up from `aio/`) |
| `pymediate/event.py` | shared `Event` + sync `EventHandler` | shared `Event` + **async** `EventHandler` |
| `pymediate/sync/` | — | new: sync `RequestHandler`, `Mediator`, `PipelineBehavior`, `EventHandler` + full-mirror `__init__` |
| `pymediate/aio/` | async classes | **deleted** |
| `pymediate/_internal/`, `pymediate/providers/` | shared internals / DI integration | unchanged |

`pymediate.sync.__init__` re-exports the shared names (`Request`, `Event`, `Services`,
`ServiceProvider`, every error) alongside its four sync variants, so sync users keep
one-line imports. The re-exports are the *same objects* as the top-level names — no
duplicated classes.

The mirror rule survives, rotated: `pymediate` (async) and `pymediate.sync` remain
structural mirrors, enforced by a parity test asserting every name in `pymediate.__all__`
appears in `pymediate.sync.__all__` as the identical object (`is`), with an explicit
intentional-variant list: `RequestHandler`, `EventHandler`, `Mediator`, `PipelineBehavior`.

**Pros:**

- Namespace finally matches positioning: the default import is the ecosystem's default mode.
- No lingering third namespace: one obvious async spelling, one obvious sync spelling.
- The parity test makes mirror drift a test failure instead of a review burden.
- `ModuleNotFoundError` on `import pymediate.aio` is honest and immediate — no half-working
  shim that hides the break until runtime behavior differs.

**Cons:**

- Every existing user of either namespace has import churn on upgrade (sync users:
  `pymediate` → `pymediate.sync`; async users: `pymediate.aio` → `pymediate`).
- Docs, examples, and every downstream snippet must be rewritten in one motion.

### Option B: Deprecation alias — keep `pymediate.aio` as a re-exporting shim for one release

**Pros:** softer landing for async users.
**Cons:** violates the locked no-back-compat-machinery constraint; ZeroVer makes the
promise implied by a deprecation cycle (stability until removal) one the project explicitly
does not offer; the shim would re-export top-level names under the old path, making two
spellings of the async API live simultaneously — the exact ambiguity the inversion exists
to remove. Rejected by maintainer decision (2026-07-10).

### Option C: Docs-only repositioning — keep both namespaces, lead all docs with `aio`

**Pros:** zero breakage.
**Cons:** the namespace keeps contradicting the positioning (`aio` still reads as the
annex); `import pymediate` remains the sync API, so the first thing a newcomer types still
lands them on the non-default side. Doesn't achieve the issue's goal. Rejected.

## Decision

Option A, exactly as locked in issue #45's decisions table:

- Hard swap; no alias, no `DeprecationWarning` module, no import hooks.
- `pymediate.sync` is a full mirror (shared names re-exported as identical objects).
- Parity enforced by a superset+identity test with the four-name intentional-variant list.
- Ships as a **minor** bump (`0.5.0`) per the ZeroVer rules; migration notes below go in
  the release changelog.
- Examples under `examples/` run against the released package and migrate in a
  post-release follow-up (issue to be filed), not in this change.

## Consequences

### Positive

- `from pymediate import RequestHandler, Mediator` gives async — the package's shape now
  argues its own positioning.
- Sync users gain one-line imports (`from pymediate.sync import ...`), completing #44's
  goal on the rotated side.
- The parity test turns the CLAUDE.md mirror rule from convention into CI enforcement for
  the `__init__` surfaces.
- One definition per shared name, verified by identity, ends any risk of the two sides'
  shared classes drifting apart.

### Negative

- Breaking for every existing import on both sides; 0.4.x pins are the escape hatch.
- The live docs site describes 0.5.0's shape from the moment this merges to `main`, while
  PyPI still serves 0.4.x until the release lands — the publish-on-push gap issue #46
  exists to close. Mitigated by releasing promptly after merge.
- `git blame` continuity breaks across the moved modules (mitigated: moves are
  whole-file where possible).

## Migration Path

Breaking change, released as `0.5.0`. Changelog notes:

| 0.4.x import | 0.5.0 import |
|---|---|
| `from pymediate.aio import RequestHandler, Mediator, PipelineBehavior, EventHandler` | `from pymediate import RequestHandler, Mediator, PipelineBehavior, EventHandler` |
| `from pymediate import RequestHandler, Mediator, PipelineBehavior, EventHandler` (sync) | `from pymediate.sync import RequestHandler, Mediator, PipelineBehavior, EventHandler` |
| `from pymediate import Request, Event, Services, ServiceProvider, <errors>` | unchanged — also importable from `pymediate.sync` |
| `from pymediate.providers.dependency_injector import ...` | unchanged |

Rules of thumb for upgrading code:

- Async code: replace every `pymediate.aio` with `pymediate`.
- Sync code: replace `pymediate` with `pymediate.sync` in imports of `RequestHandler`,
  `Mediator`, `PipelineBehavior`, `EventHandler`; imports of shared names may stay.
- There is no release where both spellings work: upgrade imports and the pin together.

## Open Questions

- Should the typing-snippet corpus rename its `async_*` stems now that async is the
  default side (e.g. unprefixed = async, `sync_*` = sync)? Tentative lean: **no** — keep
  stems stable so both expectation tables in `tests/typing/expectations.py` stay
  untouched in this change; revisit only if the corpus grows confusing.
