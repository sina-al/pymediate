# ADR 0009: Streaming handlers (`mediator.stream`)

**Status:** Proposed
**Date:** 2026-07-11
**Author:** Claude
**Reviewers:** @sina-al

## Context

PyMediate's `send()` dispatches a request to exactly one handler and returns its single,
typed response. `publish()` (ADR 0005) fans an event out to zero-or-more handlers and
returns nothing. The third messaging shape a mediator can carry — a request answered by a
**stream** of values rather than one response — has no home yet.

The July 2026 source-level survey of the six most popular Python mediator libraries
(`.claude/context/mediator-survey.md`, issue #12) found that only the single heaviest
alternative offers streaming at all, and it does so **untyped**: the stream's element type
is erased, so callers `for chunk in ...` over `Any`. Streaming is where PyMediate's
distinguishing property — end-to-end typing with definition-time validation — pays off
most directly: LLM/token streaming, paginated reads, and large exports are all
"one request, many typed chunks, consumed lazily."

The current API cannot express this. A handler under `send()` must `return` a single value;
its response type is validated at class-definition time against the request's
`Request[ResponseT]`. There is no request shape that says "I answer with a stream of
`Chunk`," no handler shape that yields, and no mediator entry point that returns an
iterator.

```python
# Today: no way to say "this request is answered by a stream of tokens."
@dataclass
class StreamCompletion(Request[???]):   # Request[str]? then send() returns one str, not many
    prompt: str
```

The design decisions below were locked with the maintainer on 2026-07-11 (recorded in this
ADR's Decision section and issue #12); this ADR records the design that satisfies them and
the alternatives rejected along the way.

## Proposed Solution(s)

### The API

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pymediate import Mediator, Services, StreamRequest, StreamRequestHandler


@dataclass
class StreamCompletion(StreamRequest[str]):   # answered by a stream of str
    prompt: str


class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
        for token in request.prompt.split():
            yield token


async def main() -> None:
    provider = Services().add(CompletionHandler()).provider()
    mediator = Mediator(provider)

    async for token in mediator.stream(StreamCompletion(prompt="hello world")):
        print(token)   # token is typed as str
```

The sync mirror is identical with `def`/`Iterator`/`for`:

```python
from collections.abc import Iterator
from pymediate.sync import Mediator, Services, StreamRequest, StreamRequestHandler


class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    def __call__(self, request: StreamCompletion) -> Iterator[str]:
        yield from request.prompt.split()


for token in mediator.stream(StreamCompletion(prompt="hello world")):
    print(token)
```

### The pieces

- **`StreamRequest[ChunkT]`** — a new base class, structurally mirroring `Request` but
  **separate from it** (it does not subclass `Request`). Its type parameter is the *element*
  type of the stream, not a response type. `StreamRequest.__init_subclass__` registers the
  chunk type the same way `Request` registers its response type. Being separate from
  `Request` is what makes misuse a **static** error: `stream()` accepts only `StreamRequest`
  and `send()` accepts only `Request`, so `send(a_stream_request)` and
  `stream(a_normal_request)` both fail type checking. This is the same separation ADR 0005
  chose for `Event` vs `Request`, for the same reason.
- **`StreamRequestHandler[StreamReqT]`** — mirrors `RequestHandler[RequestT]`, with a sync
  variant in `pymediate.sync` and the async variant at the top level (an *intentional
  variant* under the ADR 0008 mirror contract). Its `__call__` must be a **generator**:
  - async: `async def __call__(self, request: R) -> AsyncIterator[ChunkT]` containing `yield`
    (an async-generator function);
  - sync: `def __call__(self, request: R) -> Iterator[ChunkT]` containing `yield`
    (a generator function).
  Class-definition-time validation (below) enforces the generator form, the exact request
  annotation (ADR 0004), and the `Iterator[ChunkT]` / `AsyncIterator[ChunkT]` return
  annotation.
- **`InvalidStreamRequestTypeError`** — mirrors `InvalidEventTypeError`: raised when
  `StreamRequestHandler[X]` is given an `X` that isn't a `StreamRequest` subclass. New name
  in `__all__`.
- **`mediator.stream(request)`** — sync and async mirrors on the existing mediators. Returns
  `Iterator[ChunkT]` / `AsyncIterator[ChunkT]`, the element type inferred from the request's
  `StreamRequest[ChunkT]` parameter.

### Registration and validation

Streaming reuses the existing request-handler registry rather than adding a parallel one.
A `StreamRequest` subclass is a distinct type from any `Request` subclass, so the
one-handler-per-request-type registry (`_HANDLER_REGISTRY`) keys them without collision, and
the same `HandlerAlreadyRegisteredError` enforces one stream handler per stream request
type. The chunk type is stored in the same request→associated-type registry `Request` uses
(`_REQUEST_REGISTRY`); for a `StreamRequest` the associated type is its chunk type.
Consequently `_resolve_handler` and `HandlerNotFoundError` are reused verbatim — a
`stream()` with no registered handler raises `HandlerNotFoundError`, exactly as `send()`
does.

Signature validation reuses the exact-annotation machinery from `_internal/handler.py`
(ADR 0004: the request parameter must annotate the exact declared request class, because
dispatch is keyed by `type(request)`; PEP 563 string annotations resolved via
`get_type_hints`). The stream-specific differences:

- **Generator form, not coroutine.** An async-generator function is *not* a coroutine
  function (`inspect.iscoroutinefunction` returns `False` for it), so the async check is
  `inspect.isasyncgenfunction`; the sync check is `inspect.isgeneratorfunction`. A plain
  `async def`/`def` that returns an iterator without `yield` is rejected with a message that
  says to use `yield`.
- **Return annotation is the iterator, not the element.** The return annotation must be
  `AsyncIterator[ChunkT]` (async) or `Iterator[ChunkT]` (sync), where `ChunkT` is the
  chunk type declared on the `StreamRequest`. A mismatch is an
  `InvalidHandlerSignatureError` naming the expected `AsyncIterator[...]`/`Iterator[...]`
  shape. `collections.abc.Iterator`/`AsyncIterator` are the accepted spellings (the runtime
  origin `get_type_hints` produces); `typing.Iterator` resolves to the same origin.

### Locked semantics

**No runtime element-type validation.** For `send()`, `ResponseTypeMismatchError` compares
the handler's *return annotation* against the request's response type at definition time —
it never inspects a returned value. Streams keep that stance: validation checks that the
return annotation is `AsyncIterator[ChunkT]` for the declared `ChunkT`. It cannot check what
the generator actually yields without consuming it (which would defeat laziness and run side
effects), so element-level correctness is a type-checker concern, not a runtime one — the
same division of labor `send()` already has.

**Eager resolution, lazy iteration.** `stream()` resolves the handler eagerly, so a missing
registration raises `HandlerNotFoundError` at the `stream(...)` call, not on first
iteration. It then returns the handler's (async) generator, which runs only as it is
iterated. This matches the mental model — asking for a stream that has no handler is an
error you want immediately — while preserving streaming's whole point, that nothing is
computed until pulled. Concretely, `stream()` is a plain method (not itself a generator)
that returns the generator the handler produces.

**Pipeline behaviors do not wrap `stream()` in v1.** Wrapping a stream raises the same
kind of unanswered questions ADR 0005 hit for `publish`: does a behavior wrap the stream as
a unit, or run per element? Does a caching behavior buffer the whole stream? And
`PipelineBehavior`'s `next` is typed `Callable[[], Awaitable[Any]]` — a single awaited
response, not an iterator. Rather than overload that contract, streaming is behavior-exempt
in v1; a streaming-behavior design is its own ADR if demand materializes. This mirrors ADR
0005's deferral of behaviors on `publish`.

### Alternatives considered

- **Reuse `Request[AsyncIterator[Chunk]]` instead of a new base.** A streaming request would
  be an ordinary request whose response happens to be an iterator, letting `send()` return
  the iterator and reusing the entire existing path. Rejected: `send()` and `stream()` would
  both accept it, so calling the wrong one type-checks while meaning something different, and
  the chunk type would have to be un-wrapped out of `AsyncIterator[...]` at every call site.
  A dedicated `StreamRequest[ChunkT]` makes the two dispatch shapes distinguishable to the
  type checker — the property the feature exists to provide.
- **Handler returns an iterator (no `yield` required).** Allow
  `async def __call__(...) -> AsyncIterator[str]: return some_agen()`. Rejected: it muddies
  async/sync detection (a plain `async def` returning an iterator is a coroutine yielding an
  iterator, needing `await handler(req)` before iterating; a generator needs no `await`),
  forcing the mediator to branch on which form it got. The generator-only contract keeps sync
  and async structurally identical and makes definition-time detection unambiguous
  (`isgeneratorfunction` / `isasyncgenfunction`). Delegating to an existing stream stays a
  one-liner: `async for x in src: yield x`.
- **A parallel stream registry.** Rejected as needless: stream request types are disjoint
  from request types, so the existing registry keys both without ambiguity and the
  one-handler invariant, `HandlerNotFoundError`, and `_resolve_handler` all carry over
  unchanged. A second registry would duplicate that machinery for no separation benefit
  (contrast events, which are genuinely N-allowed and so *do* need their own list-valued
  registry).
- **`stream()` as a generator method (lazy resolution).** Making `stream()` itself an async
  generator would defer `HandlerNotFoundError` to first iteration. Rejected: a missing
  handler is a configuration bug that should surface when you ask for the stream, matching
  `send()`'s eager failure.
- **Behaviors wrap the stream now.** Rejected for v1 (see locked semantics) — deferred to a
  follow-up ADR, per the ADR 0005 precedent.

## Decision

Ship `StreamRequest[ChunkT]`, `StreamRequestHandler[StreamReqT]` (sync + async variants),
`InvalidStreamRequestTypeError`, and `mediator.stream()` (sync + async) as described:
dedicated base separate from `Request`, generator-only handler `__call__`, reuse of the
existing handler/associated-type registries, eager resolution with lazy iteration, no
runtime element validation, and no pipeline behaviors on streams in v1.

- **Dedicated `StreamRequest`** so `send`/`stream` misuse is a static type error — the same
  separation-of-shapes reasoning as ADR 0005's `Event`.
- **Generator-only `__call__`** for a clean sync/async mirror and unambiguous
  definition-time validation.
- **Reused registries** because stream request types are disjoint from request types; a
  parallel registry would duplicate machinery without buying separation.
- **Behaviors deferred** following ADR 0005's precedent for the newer dispatch shape.

Adds three names to `__all__` (`StreamRequest`, `StreamRequestHandler`,
`InvalidStreamRequestTypeError`) → **minor** bump per the ZeroVer policy.

## Consequences

### Positive

- Closes the streaming gap with the one property no surveyed alternative has: a **typed**
  stream (`stream()` returns `Iterator[ChunkT]`/`AsyncIterator[ChunkT]`; the handler's
  generator shape is validated at import time), symmetric across sync and async.
- `send`/`publish`/`stream` become three clearly separated dispatch shapes, each with its own
  request base and mediator entry point; existing `send`/`publish` semantics are untouched.
- Reusing `_resolve_handler`, the handler registry, and `HandlerNotFoundError` keeps the new
  surface small and its failure modes already-familiar.

### Negative

- New public surface across both mirrors (docstrings, API pages, typing snippets, an
  example) to keep in sync.
- No pipeline behaviors on streams in v1 — cross-cutting concerns around a stream (timing,
  logging, retry) live in the handler or wait for a follow-up ADR.
- Element-level type correctness rests on the static checker; a generator that yields the
  wrong type is not caught at runtime (the same limitation `send()` has for its response).

## Migration Path

No migration needed — purely additive. Existing `send()`/`publish()` code is unaffected.

## Open Questions

- Should a later version add pipeline behaviors that wrap a stream (as a unit, or per
  element)? Deferred deliberately; revisit with a concrete use case, as its own ADR.
- Should `stream()` accept a request annotated to yield a **union** of chunk types, or is the
  exact-annotation contract (ADR 0004) sufficient? Lean: exact annotation, consistent with
  the rest of the library; revisit only if a real case needs it.
