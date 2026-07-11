#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pymediate", "rich", "typer"]
# ///
# pymediate is deliberately unpinned: each run measures the latest release, and
# the run header prints the exact version it resolved to, keeping results
# attributable without a pin that would need bumping every release. rich and
# typer are output/CLI-only — they never touch the timed loops.
"""Micro-benchmark: what do mediator.send() and mediator.publish() cost over direct calls?

Deliberately measures one thing — PyMediate's dispatch overhead against the direct
call it replaces — and nothing else. It does not benchmark other libraries; overhead
numbers against a different feature set aren't comparable, and the docs quote this
script precisely because it is reproducible on any machine.

Methodology:
- ``time.perf_counter_ns`` around a tight loop of ``--number`` calls per sample
  (loop overhead is included identically in every scenario, baseline included);
- ``--repeat`` samples per scenario after a warmup batch; the median is what to
  quote, the minimum bounds the noise floor;
- the handler constructs one frozen dataclass and returns it, so dispatch — not
  work — dominates every loop;
- async scenarios time the loop inside one already-running event loop, so loop
  startup is excluded.

Progress renders on stderr, results on stdout — ``--format markdown`` and
``--format json`` pipe cleanly. Absolute numbers vary by machine and Python
build; treat published results as orders of magnitude and rerun on your own
hardware. From a repo checkout (runs against the local source):

    uv run poe benchmark

Standalone, against the latest PyPI release (the docs site serves this file;
read any script before running it from the network):

    uv run https://pymediate.sina-al.uk/benchmark.py
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import platform
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from pymediate import Event, Request, Services

# This script is unpinned and must run against any released pymediate. 0.5.0
# (ADR 0008) made async the top-level API and moved sync to pymediate.sync;
# releases before 0.4.0 also predate the ADR 0006 rename of Handler to
# RequestHandler.
try:  # pymediate >= 0.5.0: async on top, sync in pymediate.sync
    from pymediate import EventHandler as AsyncEventHandler
    from pymediate import Mediator as AsyncMediator
    from pymediate import RequestHandler as AsyncHandler
    from pymediate.sync import EventHandler, Mediator, PipelineBehavior, RequestHandler
except ModuleNotFoundError:  # pymediate < 0.5.0: sync on top, async in pymediate.aio
    from pymediate.aio import EventHandler as AsyncEventHandler  # type: ignore[no-redef]
    from pymediate.aio import Mediator as AsyncMediator  # type: ignore[no-redef]

    from pymediate import EventHandler, Mediator, PipelineBehavior  # type: ignore[no-redef]

    try:
        from pymediate.aio import RequestHandler as AsyncHandler  # type: ignore[no-redef]

        from pymediate import RequestHandler  # type: ignore[no-redef]
    except ImportError:  # pymediate < 0.4.0
        from pymediate.aio import Handler as AsyncHandler  # type: ignore[attr-defined, no-redef]

        from pymediate import Handler as RequestHandler  # type: ignore[attr-defined, no-redef]


@dataclass(frozen=True)
class Pong:
    value: int


@dataclass(frozen=True)
class Ping(Request[Pong]):
    value: int


class PingHandler(RequestHandler[Ping]):
    def __call__(self, request: Ping) -> Pong:
        return Pong(request.value)


class NoOpBehavior(PipelineBehavior[Ping]):
    def __call__(self, request: Ping, next: Callable[[], Any]) -> Any:
        return next()


# A request type gets exactly one handler, enforced at class definition — so the
# async scenarios need their own request type rather than reusing Ping.
@dataclass(frozen=True)
class AsyncPing(Request[Pong]):
    value: int


class AsyncPingHandler(AsyncHandler[AsyncPing]):
    async def __call__(self, request: AsyncPing) -> Pong:
        return Pong(request.value)


# publish() scenarios use one subscriber so every row stays one-unit-of-work
# against the direct-call baseline; each event type is dedicated to its group.
@dataclass(frozen=True)
class Pinged(Event):
    value: int


class PingedHandler(EventHandler[Pinged]):
    def __call__(self, event: Pinged) -> None:
        return None


@dataclass(frozen=True)
class AsyncPinged(Event):
    value: int


class AsyncPingedHandler(AsyncEventHandler[AsyncPinged]):
    async def __call__(self, event: AsyncPinged) -> None:
        return None


def bench_sync(
    fn: Callable[[], object],
    *,
    number: int,
    repeat: int,
    warmup: int,
    on_sample: Callable[[], None],
) -> list[float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter_ns()
        for _ in range(number):
            fn()
        samples.append((time.perf_counter_ns() - start) / number)
        on_sample()
    return samples


def bench_async(
    fn: Callable[[], Awaitable[object]],
    *,
    number: int,
    repeat: int,
    warmup: int,
    on_sample: Callable[[], None],
) -> list[float]:
    async def run_samples() -> list[float]:
        for _ in range(warmup):
            await fn()
        samples: list[float] = []
        for _ in range(repeat):
            start = time.perf_counter_ns()
            for _ in range(number):
                await fn()
            samples.append((time.perf_counter_ns() - start) / number)
            on_sample()
        return samples

    return asyncio.run(run_samples())


@dataclass(frozen=True)
class Scenario:
    name: str
    # "sync" | "async" | "sync-publish" | "async-publish" — ratios are computed within a
    # group, so publish() is measured against a direct call to its own (None-returning)
    # event handler, not against the request handler's baseline.
    group: str
    is_baseline: bool
    run: Callable[[Callable[[], None]], list[float]]


@dataclass(frozen=True)
class Result:
    scenario: Scenario
    samples: list[float]

    @property
    def median(self) -> float:
        return statistics.median(self.samples)

    @property
    def minimum(self) -> float:
        return min(self.samples)


class Group(StrEnum):
    all = "all"
    sync = "sync"
    async_ = "async"


class Format(StrEnum):
    pretty = "pretty"
    markdown = "markdown"
    json = "json"


def build_scenarios(
    *, number: int, repeat: int, warmup: int, behaviors: int, only: Group
) -> list[Scenario]:
    request = Ping(value=1)
    async_request = AsyncPing(value=1)
    event = Pinged(value=1)
    async_event = AsyncPinged(value=1)

    sync_handler = PingHandler()
    sync_mediator = Mediator(Services().add(PingHandler()).provider())
    behavior_services = Services().add(PingHandler())
    for _ in range(behaviors):
        behavior_services.add(NoOpBehavior())
    behavior_mediator = Mediator(behavior_services.provider())
    event_handler = PingedHandler()
    publish_mediator = Mediator(Services().add(PingedHandler()).provider())

    async_handler = AsyncPingHandler()
    async_mediator = AsyncMediator(Services().add(AsyncPingHandler()).provider())
    async_event_handler = AsyncPingedHandler()
    async_publish_mediator = AsyncMediator(Services().add(AsyncPingedHandler()).provider())

    kwargs = {"number": number, "repeat": repeat, "warmup": warmup}
    plural = "behavior" if behaviors == 1 else "behaviors"
    scenarios = [
        Scenario(
            "sync: handler(request) — direct call",
            "sync",
            True,
            lambda tick: bench_sync(lambda: sync_handler(request), on_sample=tick, **kwargs),
        ),
        Scenario(
            "sync: mediator.send(request)",
            "sync",
            False,
            lambda tick: bench_sync(lambda: sync_mediator.send(request), on_sample=tick, **kwargs),
        ),
        Scenario(
            f"sync: send() + {behaviors} pipeline {plural}",
            "sync",
            False,
            lambda tick: bench_sync(
                lambda: behavior_mediator.send(request), on_sample=tick, **kwargs
            ),
        ),
        Scenario(
            "sync: handler(event) — direct call",
            "sync-publish",
            True,
            lambda tick: bench_sync(lambda: event_handler(event), on_sample=tick, **kwargs),
        ),
        Scenario(
            "sync: mediator.publish(event) — 1 subscriber",
            "sync-publish",
            False,
            lambda tick: bench_sync(
                lambda: publish_mediator.publish(event), on_sample=tick, **kwargs
            ),
        ),
        Scenario(
            "async: await handler(request) — direct call",
            "async",
            True,
            lambda tick: bench_async(
                lambda: async_handler(async_request), on_sample=tick, **kwargs
            ),
        ),
        Scenario(
            "async: await mediator.send(request)",
            "async",
            False,
            lambda tick: bench_async(
                lambda: async_mediator.send(async_request), on_sample=tick, **kwargs
            ),
        ),
        Scenario(
            "async: await handler(event) — direct call",
            "async-publish",
            True,
            lambda tick: bench_async(
                lambda: async_event_handler(async_event), on_sample=tick, **kwargs
            ),
        ),
        Scenario(
            "async: await mediator.publish(event) — 1 subscriber",
            "async-publish",
            False,
            lambda tick: bench_async(
                lambda: async_publish_mediator.publish(async_event), on_sample=tick, **kwargs
            ),
        ),
    ]
    if behaviors == 0:
        scenarios = [s for s in scenarios if "pipeline" not in s.name]
    if only is not Group.all:
        scenarios = [s for s in scenarios if s.group.startswith(only.value)]
    return scenarios


def ratio_for(result: Result, baselines: dict[str, float]) -> float | None:
    if result.scenario.is_baseline:
        return None
    baseline = baselines.get(result.scenario.group)
    return result.median / baseline if baseline else None


def render_pretty(out: Console, results: list[Result], baselines: dict[str, float]) -> None:
    table = Table(header_style="bold", row_styles=None, pad_edge=False)
    table.add_column("Scenario")
    table.add_column("Median / call", justify="right")
    table.add_column("Min / call", justify="right")
    table.add_column("vs direct call", justify="right")
    for result in results:
        ratio = ratio_for(result, baselines)
        style = "dim" if result.scenario.is_baseline else None
        table.add_row(
            result.scenario.name,
            f"{result.median:,.0f} ns",
            f"{result.minimum:,.0f} ns",
            "[dim]baseline[/dim]" if ratio is None else f"[bold cyan]{ratio:.1f}x[/bold cyan]",
            style=style,
        )
    out.print(table)

    sync_results = [r for r in results if r.scenario.group == "sync"]
    direct = next((r for r in sync_results if r.scenario.is_baseline), None)
    send = next((r for r in sync_results if not r.scenario.is_baseline), None)
    if direct and send:
        overhead_us = (send.median - direct.median) / 1000
        out.print(
            f"Routing a request through the mediator costs about [bold]{overhead_us:.1f} µs[/bold]"
            " more per call than calling the handler directly on this machine."
        )
    out.print(
        "[dim]Numbers are machine-dependent — treat them as orders of magnitude."
        " Rerun with --help for the knobs.[/dim]"
    )


def render_markdown(results: list[Result], baselines: dict[str, float]) -> None:
    print("| Scenario | median ns/call | min ns/call | vs direct call |")
    print("| --- | ---: | ---: | ---: |")
    for result in results:
        ratio = ratio_for(result, baselines)
        ratio_text = "1.0x (baseline)" if ratio is None else f"{ratio:.1f}x"
        print(
            f"| {result.scenario.name} | {result.median:,.0f} | {result.minimum:,.0f}"
            f" | {ratio_text} |"
        )
    print()
    print("Numbers are machine-dependent; rerun locally with: uv run poe benchmark")


def render_json(results: list[Result], baselines: dict[str, float], config: dict[str, Any]) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "pymediate": importlib.metadata.version("pymediate"),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "config": config,
        "results": [
            {
                "scenario": result.scenario.name,
                "group": result.scenario.group,
                "baseline": result.scenario.is_baseline,
                "median_ns": result.median,
                "min_ns": result.minimum,
                "ratio_vs_direct": ratio_for(result, baselines),
                "samples_ns": result.samples,
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2))


def print_header(console: Console, *, number: int, repeat: int, warmup: int) -> None:
    console.print(
        f"[bold]pymediate[/bold] {importlib.metadata.version('pymediate')}"
        f" · Python {platform.python_version()} ({platform.python_implementation()})"
        f" · {platform.platform()}"
    )
    console.print(
        f"[dim]{repeat} samples × {number:,} calls per scenario,"
        f" after {warmup:,} warmup calls[/dim]"
    )
    console.print()


app = typer.Typer(add_completion=False)


@app.command()
def main(
    number: Annotated[
        int, typer.Option("--number", "-n", min=1, help="Calls per sample.")
    ] = 100_000,
    repeat: Annotated[
        int,
        typer.Option(
            "--repeat", "-r", min=1, help="Samples per scenario; the median is the quotable figure."
        ),
    ] = 5,
    warmup: Annotated[
        int, typer.Option(min=0, help="Warmup calls per scenario, before sampling starts.")
    ] = 1_000,
    behaviors: Annotated[
        int,
        typer.Option(
            min=0, help="No-op pipeline behaviors in the pipeline scenario; 0 skips that scenario."
        ),
    ] = 1,
    only: Annotated[
        Group, typer.Option(help="Run only the sync or only the async scenarios.")
    ] = Group.all,
    format: Annotated[
        Format,
        typer.Option(
            "--format",
            "-f",
            help="pretty for a terminal, markdown for the docs table, json for scripting.",
        ),
    ] = Format.pretty,
) -> None:
    """Measure what mediator.send() and mediator.publish() cost over direct calls.

    Runs each scenario as a tight loop of NUMBER calls, REPEAT times, and reports
    the median — dispatch overhead, not handler work, dominates every loop. The
    publish scenarios use a single subscriber and their own direct-call baseline
    (the event handler returns None, so it does less work than the request
    handler), keeping every ratio one unit of work against its own baseline.
    The defaults match the methodology quoted in the docs; results always print
    the exact pymediate version they measured.
    """
    out = Console()
    err = Console(stderr=True)

    # The header goes out before any measuring starts, so a network-fetched run
    # shows life immediately. For JSON it moves to stderr to keep stdout pure.
    if format is Format.pretty:
        print_header(out, number=number, repeat=repeat, warmup=warmup)
    elif format is Format.markdown:
        print(f"pymediate {importlib.metadata.version('pymediate')}")
        print(f"Python {platform.python_version()} ({platform.python_implementation()})")
        print(f"Platform: {platform.platform()}")
        print(f"Samples: {repeat} x {number} calls (after {warmup} warmup calls)")
        print()
    else:
        print_header(err, number=number, repeat=repeat, warmup=warmup)

    scenarios = build_scenarios(
        number=number, repeat=repeat, warmup=warmup, behaviors=behaviors, only=only
    )

    results: list[Result] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=err,
        transient=True,
        disable=not err.is_terminal,
    )
    with progress:
        task = progress.add_task("warming up", total=len(scenarios) * repeat)
        for scenario in scenarios:
            progress.update(task, description=scenario.name)
            samples = scenario.run(lambda: progress.advance(task))
            results.append(Result(scenario, samples))

    baselines = {r.scenario.group: r.median for r in results if r.scenario.is_baseline}

    if format is Format.pretty:
        render_pretty(out, results, baselines)
    elif format is Format.markdown:
        render_markdown(results, baselines)
    else:
        config = {"number": number, "repeat": repeat, "warmup": warmup, "behaviors": behaviors}
        render_json(results, baselines, config)


if __name__ == "__main__":
    app()
