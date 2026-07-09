#!/usr/bin/env python3
"""Micro-benchmark: what does mediator.send() cost over calling the handler directly?

Deliberately measures one thing — PyMediate's dispatch overhead against the direct
call it replaces — and nothing else. It does not benchmark other libraries; overhead
numbers against a competitor's different feature set aren't comparable, and the docs
quote this script precisely because it is reproducible on any machine.

Methodology:
- ``time.perf_counter_ns`` around a tight loop of ``--number`` calls per sample
  (loop overhead is included identically in every scenario, baseline included);
- ``--repeat`` samples per scenario after a warmup batch; the median is what to
  quote, the minimum bounds the noise floor;
- the handler constructs one frozen dataclass and returns it, so dispatch — not
  work — dominates every loop;
- async scenarios time the loop inside one already-running event loop, so loop
  startup is excluded.

Absolute numbers vary by machine and Python build; treat published results as
orders of magnitude and rerun locally:

    uv run poe benchmark
"""

from __future__ import annotations

import argparse
import asyncio
import platform
import statistics
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymediate import Handler, Mediator, PipelineBehavior, Request, Services
from pymediate.aio import Handler as AsyncHandler
from pymediate.aio import Mediator as AsyncMediator


@dataclass(frozen=True)
class Pong:
    value: int


@dataclass(frozen=True)
class Ping(Request[Pong]):
    value: int


class PingHandler(Handler[Ping]):
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


def bench_sync(fn: Callable[[], object], *, number: int, repeat: int, warmup: int) -> list[float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter_ns()
        for _ in range(number):
            fn()
        samples.append((time.perf_counter_ns() - start) / number)
    return samples


def bench_async(
    fn: Callable[[], Awaitable[object]], *, number: int, repeat: int, warmup: int
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
        return samples

    return asyncio.run(run_samples())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--number", type=int, default=100_000, help="calls per sample (default: 100000)"
    )
    parser.add_argument("--repeat", type=int, default=5, help="samples per scenario (default: 5)")
    parser.add_argument(
        "--warmup", type=int, default=1_000, help="warmup calls per scenario (default: 1000)"
    )
    args = parser.parse_args()

    request = Ping(value=1)
    async_request = AsyncPing(value=1)

    sync_handler = PingHandler()
    sync_mediator = Mediator(Services().add(PingHandler()).provider())
    behavior_mediator = Mediator(Services().add(PingHandler()).add(NoOpBehavior()).provider())

    async_handler = AsyncPingHandler()
    async_mediator = AsyncMediator(Services().add(AsyncPingHandler()).provider())

    kwargs = {"number": args.number, "repeat": args.repeat, "warmup": args.warmup}
    scenarios: list[tuple[str, list[float], str | None]] = [
        (
            "sync: handler(request) — direct call",
            bench_sync(lambda: sync_handler(request), **kwargs),
            None,
        ),
        (
            "sync: mediator.send(request)",
            bench_sync(lambda: sync_mediator.send(request), **kwargs),
            "sync",
        ),
        (
            "sync: send() + 1 pipeline behavior",
            bench_sync(lambda: behavior_mediator.send(request), **kwargs),
            "sync",
        ),
        (
            "async: await handler(request) — direct call",
            bench_async(lambda: async_handler(async_request), **kwargs),
            None,
        ),
        (
            "async: await mediator.send(request)",
            bench_async(lambda: async_mediator.send(async_request), **kwargs),
            "async",
        ),
    ]

    baselines = {
        "sync": statistics.median(scenarios[0][1]),
        "async": statistics.median(scenarios[3][1]),
    }

    print(f"Python {platform.python_version()} ({platform.python_implementation()})")
    print(f"Platform: {platform.platform()}")
    print(f"Samples: {args.repeat} x {args.number} calls (after {args.warmup} warmup calls)")
    print()
    print("| Scenario | median ns/call | min ns/call | vs direct call |")
    print("| --- | ---: | ---: | ---: |")
    for name, samples, baseline_key in scenarios:
        median = statistics.median(samples)
        low = min(samples)
        if baseline_key is None:
            ratio = "1.0x (baseline)"
        else:
            ratio = f"{median / baselines[baseline_key]:.1f}x"
        print(f"| {name} | {median:,.0f} | {low:,.0f} | {ratio} |")
    print()
    print("Numbers are machine-dependent; rerun locally with: uv run poe benchmark")
    return 0


if __name__ == "__main__":
    sys.exit(main())
