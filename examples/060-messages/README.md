# 060-messages

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F060-messages%2Fdevcontainer.json)

How should you design your request objects? PyMediate requests are just dataclasses — and
the small decisions on them carry real weight. Make one `frozen=True` and it becomes an
immutable, hashable value object you can use as a cache key. Add a `__post_init__` and a
malformed request fails *at construction*, before any handler runs. Mark a field
`repr=False` and its secret stays out of your logs. This example shows each of those on a
task board.

## Run it

```bash
cd examples/060-messages
uv sync
uv run taskboard
```

```text
Created task 1: title='Write the report'
A frozen request can't be mutated after construction
Invalid request rejected at construction: title cannot be empty
SearchByTag cache hits across 2 identical searches: 1
Webhook request repr (secret hidden): RegisterWebhook(url='https://example.com/hook')
```

Each line is one design choice paying off: normalization on the way in, immutability, a
construction-time rejection, a frozen request serving as its own cache key, and a secret
kept out of the printed request.

## The money shot: a frozen, validated request

```python
@dataclass(frozen=True, slots=True)
class CreateTask(Request[Task]):
    title: str
    tags: tuple[str, ...] = ()
    priority: int = 3

    def __post_init__(self) -> None:
        # Frozen dataclasses block plain assignment, so normalize via object.__setattr__.
        object.__setattr__(self, "title", self.title.strip())
        if not self.title:
            raise ValueError("title cannot be empty")
        if not 1 <= self.priority <= 5:
            raise ValueError("priority must be between 1 and 5")
```

`CreateTask("   ")` raises `ValueError` immediately — no mediator, no handler involved. By
the time a handler receives a `CreateTask`, it's already normalized and known-good, so the
handler doesn't re-check anything. Bad data never travels.

## Four choices, four payoffs

| Choice | What it buys | Where to look |
| --- | --- | --- |
| `frozen=True` | Immutable in flight; hashable, so the request is its own cache key. | `SearchByTag` — the handler caches on the request instance. |
| `__post_init__` | Normalize + validate at construction; invalid requests never dispatch. | Every request; `CreateTask` and `SearchByTag` normalize too. |
| `field(repr=False)` | A secret stays out of `repr`, logs, and tracebacks. | `RegisterWebhook.secret`. |
| A frozen mixin | Shared fields *and* their validation across request types. | `PaginationMixin` → `SearchByTag`. |

The frozen-as-cache-key trick is worth dwelling on: two `SearchByTag(tag="work")` values
are `==` and hash-equal, so the handler's `dict[SearchByTag, list[Task]]` cache treats them
as the same key — the second search never touches the store. `slots=True` on `CreateTask`
trims per-instance memory for high-volume types; it's optional.

## The files

| File | What it is |
| --- | --- |
| [`src/taskboard/messages.py`](src/taskboard/messages.py) | **Start here.** The three requests and the pagination mixin — every design choice, annotated. |
| [`src/taskboard/handlers.py`](src/taskboard/handlers.py) | Deliberately thin handlers — no re-validation, because the messages did it. |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | `Task`, `Webhook`, and the in-memory store the handlers use. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | `build_mediator` and the demo. |
| [`tests/test_messages.py`](tests/test_messages.py) | Asserts construction-time failure, immutability, the frozen cache key, and the hidden secret: `uv run pytest` → `9 passed`. |

## Small print

- This example is about the request *object*. **Where** validation should live — a Pydantic
  DTO at the edge vs. a command in the core — is a separate decision, covered in
  [065-validation](../065-validation/).
- `object.__setattr__` is the sanctioned way to normalize a frozen dataclass in
  `__post_init__`; plain assignment raises `FrozenInstanceError`.
- A frozen request can only be a cache key if its fields are themselves hashable — note
  `tags: tuple[str, ...]`, not `list[str]`. A `list` field would make the request
  unhashable.

## Where next

- [060-messages-sync](../060-messages-sync/) — the same message designs on `pymediate.sync`
  (the dataclasses are identical; only the handlers change).
- [065-validation](../065-validation/) — the placement decision: edge DTO vs. core command.
- The docs: [dataclasses guide](https://pymediate.sina-al.uk/docs/guide/dataclasses).
