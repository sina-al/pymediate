# Mediator ecosystem survey — anonymized knowledge base

Maintained by the `/compare` skill; humans review, the skill writes. This file backs
`docs.v2/content/docs/comparison.mdx` — every claim on that page must trace to a fact here.

**NEVER put library names, URLs, star counts, download counts, or any other identifying
detail in this file.** This repo is public and the comparison page is deliberately
anonymous; identity would leak from here. Libraries get stable codenames (Library A–F).
The codename → identity mapping lives in the maintainer's private Claude memory, not in
this repository.

## Survey metadata

- **Last full survey:** July 2026 (source-level read of dispatch code, registries, and
  type signatures — not READMEs).
- **Selection criterion:** the six most popular mediator libraries in the Python
  ecosystem, ranked by GitHub stars and PyPI downloads at survey time. Re-derive this
  list fresh on each re-survey; the criterion is objective, so the set is reproducible
  without storing identities.
- **Provenance:** survey performed for the README/docs "Why PyMediate?" claims and
  issue #15 (closed 2026-07-09 by the comparison page). Per-library profiles below are
  incomplete because only aggregate findings were recorded at the time — fill them in
  at the next full re-survey, and write the identity map to private memory then.

## Aggregate findings (July 2026)

| Capability | Finding across the six |
| --- | --- |
| Request-to-handler link | Class-name strings, naming conventions, or a separate `bind(request, handler)` call; none key dispatch on the class via a type parameter. |
| Response typing at call site | All six: `object`, `Any`, or a generic not actually bound to the request. |
| Handler signature validation | None of the six validate at class-definition time; mistakes surface at dispatch (runtime). |
| Duplicate registration | Silently overwrites the original handler, or silently ignores the new one; none raise. |
| Sync API | Almost all async-only; synchronous codebases must adopt an event loop. |
| Event publishing (one request, many handlers) | Five of six have it; every implementation is type-erased or async-only. PyMediate gap → issue #10. |
| Streaming responses | One of six offers it (the largest library), untyped. PyMediate gap → issue #12. |
| Runtime dependencies | Varies; several require a serialization framework or a dependency-injection container to participate at all. |

## Per-library profiles

To be filled at the next full re-survey. For each of Library A–F record: dispatch
mechanism, registry keying, `send()` return typing, duplicate-registration behavior,
sync/async surface, event publishing (and whether typed), streaming (and whether typed),
required runtime dependencies, approximate SLOC of the dispatch core. No identifying
details (see warning above).

- **Library A:** not yet profiled.
- **Library B:** not yet profiled.
- **Library C:** not yet profiled.
- **Library D:** not yet profiled.
- **Library E:** not yet profiled.
- **Library F:** not yet profiled.

## PyMediate roadmap items that change the comparison

Check these on every run (`gh issue view <n> --json state`); a closed item means the
docs row and the matching aggregate finding above must be updated.

| Issue | Capability | Comparison row today |
| --- | --- | --- |
| #10 | Event publishing (`mediator.publish`) | "Not yet — planned in issue #10" |
| #12 | Streaming handlers (`mediator.stream`) | "Not yet — planned in issue #12" |
| #11 | Scoped registries | No row yet; add one if it ships and alternatives were surveyed for it |
| #13 | contrib module of zero-dependency behaviors | No row yet |
| #14 | Function-based handlers (may be rejected) | No row yet |

## Published benchmark results

Quoted on the comparison page; replace only with numbers from a fresh local run of
`uv run poe benchmark` (full defaults), never by editing figures in place.

- **Last run:** 2026-07-09, pymediate 0.1.5 (dev checkout), Python 3.13.0 (CPython),
  2020 Intel MacBook Pro, macOS 15.7. Medians of five samples of 100,000 calls.

| Scenario | Median per call | Relative to direct call |
| --- | ---: | ---: |
| Sync: direct call | 0.34 µs | Baseline |
| Sync: `mediator.send()` | 1.8 µs | 5.5x |
| Sync: `send()` plus one pipeline behavior | 8.3 µs | 24.8x |
| Async: direct call | 0.42 µs | Baseline |
| Async: `await mediator.send()` | 2.1 µs | 5.0x |

Methodology and its rationale live in `scripts/benchmark.py`'s docstring. The script is
PEP 723 (`uv run https://pymediate.sina-al.uk/benchmark.py`), copied to the site root by
`docs.v2`'s build script; `pymediate` stays deliberately unpinned there (each run measures
the latest release, and the run header prints the exact version). Its other deps (rich,
typer) are output/CLI-only and never touch the timed loops. Quotable runs use the full
defaults with `--format markdown`; `--only`, `--behaviors`, and `--format json` exist for
exploration, not for the published table.
