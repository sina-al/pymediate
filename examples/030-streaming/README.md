# 030-streaming

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F030-streaming%2Fdevcontainer.json)

**How do I return results incrementally?** When the answer arrives a piece at a time — LLM
tokens, paginated rows, a large export — you don't want one big response after a long wait.
`stream()` is the mediator's third dispatch shape: one request answered by a **lazy feed of
typed chunks**. This example streams a fake LLM completion, one token (`str`) at a time.

## Run it

```bash
cd examples/030-streaming
uv sync
uv run python app.py
```

```text
Streaming a completion:
  received 'A' (model has emitted 1 so far)
  received 'mediator' (model has emitted 2 so far)
  received 'routes' (model has emitted 3 so far)
  ...
  received '.' (model has emitted 10 so far)

Broke early after ['A', 'mediator', 'routes']
Model emitted only 3 tokens — the rest were never produced

Unregistered stream raised HandlerNotFoundError at the call, before iteration
```

## The idea: a handler that yields

A `StreamRequest[ChunkT]` declares the type of each chunk. Its handler's `__call__` is an
**async generator** — it `yield`s chunks instead of `return`ing a value:

```python
@dataclass
class StreamCompletion(StreamRequest[str]):   # a stream of str chunks
    prompt: str

class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
        async for token in self._model.stream(request.prompt):
            yield token                       # each token is a str, end to end
```

Consume it with `async for` — every `token` is typed `str`, no casts:

```python
async for token in mediator.stream(StreamCompletion(prompt="Explain a mediator")):
    print(token)
```

`send()` returns one response; `publish()` returns nothing; `stream()` returns an
`AsyncIterator[ChunkT]`. The chunk type is declared once on `StreamRequest[str]` and flows
all the way to the consumer.

## Eager resolution, lazy iteration

Two things happen at different times, and this example makes both visible:

- **The handler is resolved eagerly**, at the `stream()` call. An unregistered request
  raises `HandlerNotFoundError` right there, before you pull a single chunk — a missing
  handler is a config bug you want to see immediately, not on first iteration.
- **The stream itself is lazy.** The handler's body runs only as you pull chunks. The demo's
  fake model records each token as it emits it, so the "emitted" count stays in lockstep with
  what you've consumed — and breaking early proves the remaining tokens are *never generated*.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The stream request, the generator handler, a fake token source, and a demo of lazy streaming, an early break, and eager resolution. |
| [`test_app.py`](test_app.py) | Asserts the exact chunk sequence, that production never runs ahead of consumption, that an early break stops production, and that an unregistered stream raises eagerly. `uv run pytest` → `5 passed`. |

## Small print

- **Pipeline behaviors do not wrap streams.** Behaviors run on `send()` only — a
  single-response middleware contract can't answer whether it should wrap a stream as a unit
  or run per chunk. Cross-cutting concerns around a stream (timing, logging, retry) live in
  the handler for now.
- The handler `__call__` must be an **async generator** (contain `yield`). A plain
  `async def` that merely *returns* an iterator is rejected when the class is defined, not at
  dispatch time.
- Keep the handler lazy: stream from the source rather than building the whole result up
  front and yielding from a list, so memory stays flat.

## Where next

- [030-streaming-sync](../030-streaming-sync/) — this exact stream without the event loop,
  on `pymediate.sync` (`Iterator`, plain `for`).
- The docs: [streaming guide](https://pymediate.sina-al.uk/docs/guide/streaming) ·
  [StreamRequestHandler](https://pymediate.sina-al.uk/docs/api/stream-request-handler).
