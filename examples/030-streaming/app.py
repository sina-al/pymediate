"""Large language model (LLM) token streaming on PyMediate's asynchronous API.

Demonstrates the mediator's third dispatch shape: ``stream``. Where ``send`` returns one
typed response and ``publish`` fans an event out to many handlers, ``stream`` answers one
request with a **lazy feed of typed chunks** — here, an LLM completion arriving one token
(a ``str``) at a time. The handler's ``__call__`` is an *async generator*: it ``yield``\\s
chunks instead of ``return``\\ing a value.

Two properties are made observable through a deterministic fake model:

* **Eager resolution, lazy iteration.** ``mediator.stream(...)`` resolves the handler at the
  call — an unregistered request raises immediately — but the handler's body runs only as you
  pull chunks with ``async for``.
* **Nothing is produced ahead of consumption.** The model records each token as it emits it,
  so breaking early provably stops production of the remaining tokens.

The LLM domain is a standalone illustration — it deliberately steps away from the task-board
domain the other examples share, because token streaming is where readers arrive asking for
``stream``. The sync mirror of this example is 030-streaming-sync, built on ``pymediate.sync``.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pymediate import (
    HandlerNotFoundError,
    Mediator,
    Services,
    StreamRequest,
    StreamRequestHandler,
)

# The canned completion the fake model streams back, one token at a time. Keeping it a
# module constant lets the tests assert the exact chunk sequence.
COMPLETION: tuple[str, ...] = (
    "A",
    "mediator",
    "routes",
    "each",
    "request",
    "to",
    "its",
    "one",
    "handler",
    ".",
)


class FakeLanguageModel:
    """A deterministic stand-in for a streaming LLM client.

    Yields a canned completion one token at a time, appending each token to ``emitted``
    as it leaves the model. That per-token side effect is what lets the demo and the tests
    watch production interleave with consumption, and prove that tokens past an early break
    are never generated.
    """

    def __init__(self, emitted: list[str]) -> None:
        self._emitted = emitted

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream the completion token by token, recording each as it is emitted."""
        for token in COMPLETION:
            await asyncio.sleep(0)  # stands in for a per-token network round-trip
            self._emitted.append(token)
            yield token


# ---- Stream requests: each declares the type of chunk its stream yields ----


@dataclass
class StreamCompletion(StreamRequest[str]):
    """Ask the model to complete a prompt; answered by a stream of token strings."""

    prompt: str


@dataclass
class StreamAudioClip(StreamRequest[bytes]):
    """A second stream request with no registered handler.

    It exists only to show eager resolution: streaming it raises ``HandlerNotFoundError``
    at the ``stream()`` call, before any chunk is pulled.
    """

    clip_id: str


# ---- Stream handler: exactly one per request type; __call__ is an async generator ----


class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    """Streams the model's completion token by token.

    ``__call__`` is an *async generator* — it ``yield``\\s each ``str`` rather than
    returning a value. Delegating to an existing async stream (an LLM client, a DB cursor)
    stays a one-liner: iterate the source, re-yield each chunk.
    """

    def __init__(self, model: FakeLanguageModel) -> None:
        self._model = model

    async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
        async for token in self._model.stream(request.prompt):
            yield token


def build_mediator(emitted: list[str] | None = None) -> Mediator:
    """Wire a mediator with one stream handler backed by the fake model.

    Args:
        emitted: A sink the model appends each emitted token to, so callers can observe
            exactly what was produced. A fresh list is used when omitted.
    """
    emitted = emitted if emitted is not None else []
    services = Services()
    services.add(CompletionHandler(FakeLanguageModel(emitted)))
    return Mediator(services.provider())


async def main() -> None:
    """Run a short demo: lazy streaming, an early break, and eager resolution."""
    emitted: list[str] = []
    mediator = build_mediator(emitted)

    # 1) Lazy iteration: each token is produced only as we pull it. The model's emitted
    #    count stays in lockstep with what we've received — never running ahead.
    print("Streaming a completion:")
    async for token in mediator.stream(StreamCompletion(prompt="Explain a mediator")):
        print(f"  received {token!r} (model has emitted {len(emitted)} so far)")

    # 2) Early break: stop after three tokens. The remaining tokens are never generated.
    emitted.clear()
    received: list[str] = []
    async for token in mediator.stream(StreamCompletion(prompt="Explain a mediator")):
        received.append(token)
        if len(received) == 3:
            break
    print(f"\nBroke early after {received}")
    print(f"Model emitted only {len(emitted)} tokens — the rest were never produced")

    # 3) Eager resolution: an unregistered stream request raises at the stream() call,
    #    before any chunk is pulled, so a missing handler is reported before iteration.
    try:
        mediator.stream(StreamAudioClip(clip_id="clip-1"))
    except HandlerNotFoundError:
        print("\nUnregistered stream raised HandlerNotFoundError at the call, before iteration")


if __name__ == "__main__":
    asyncio.run(main())
