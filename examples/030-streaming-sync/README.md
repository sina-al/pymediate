# 030-streaming-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F030-streaming-sync%2Fdevcontainer.json)

`pymediate.sync.Mediator.stream()` returns results incrementally instead of building one
complete response first. This example uses a simulated large language model (LLM) to yield
one typed token (`str`) at a time through an `Iterator`.

## Run

From this example directory:

```bash
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

## Yield typed chunks

A `StreamRequest[ChunkT]` declares the type of each chunk. Its handler's `__call__` is a
**generator** — it `yield`s chunks instead of `return`ing a value:

```python
@dataclass
class StreamCompletion(StreamRequest[str]):   # a stream of str chunks
    prompt: str

class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    def __call__(self, request: StreamCompletion) -> Iterator[str]:
        yield from self._model.stream(request.prompt)   # each chunk is a str, end to end
```

Consume it with a plain `for` — every `token` is typed `str`, no casts:

```python
for token in mediator.stream(StreamCompletion(prompt="Explain a mediator")):
    print(token)
```

`send()` returns one response; `publish()` returns nothing; `stream()` returns an
`Iterator[ChunkT]`. The chunk type is declared once on `StreamRequest[str]` and flows all
the way to the consumer. The only delta from the async twin is `def`/`Iterator`/`for` in
place of `async def`/`AsyncIterator`/`async for`.

## Resolve the handler before iteration

Two things happen at different times, and this example makes both visible:

- **The handler is resolved eagerly**, at the `stream()` call. An unregistered request
  raises `HandlerNotFoundError` right there, before you pull a single chunk. A missing
  handler is a configuration error reported before iteration.
- **The stream itself is lazy.** The handler's body runs only as you pull chunks. The demo's
  fake model records each token as it emits it, so the "emitted" count stays in lockstep with
  what you've consumed — and breaking early proves the remaining tokens are *never generated*.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The stream request, the generator handler, a fake token source, and a demo of lazy streaming, an early break, and eager resolution. |
| [`test_app.py`](test_app.py) | Asserts the exact chunk sequence, that production never runs ahead of consumption, that an early break stops production, and that an unregistered stream raises eagerly. `uv run pytest` → `5 passed`. |

## Details

- **Pipeline behaviors do not wrap streams.** They run on `send()` only. Put stream timing,
  logging, or retry logic around source iteration in the stream handler.
- The handler `__call__` must be a **generator** (contain `yield`). A plain `def` that merely
  *returns* an iterator is rejected when the class is defined, not at dispatch time.
- Yield chunks as the source produces them. Building a list first delays the first result
  and stores the complete response in memory.

## Where next

- [040-pipeline-behaviors-sync](../040-pipeline-behaviors-sync/) — apply logging,
  authorization, caching, and a transaction boundary around synchronous request handlers.
- [030-streaming](../030-streaming/) — the asynchronous version
  (`AsyncIterator` and `async for`).
- The docs: [streaming guide](https://pymediate.sina-al.uk/docs/guide/streaming) ·
  [StreamRequestHandler](https://pymediate.sina-al.uk/docs/api/stream-request-handler).
