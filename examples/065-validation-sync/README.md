# 065-validation-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F065-validation-sync%2Fdevcontainer.json)

The synchronous mirror of [065-validation](../065-validation/), on `pymediate.sync`. Same
answer to "where does validation go?" — **shape at the edge** (Pydantic, FastAPI) and
**invariants in the core** (no Pydantic) — with plain `def` endpoints and a synchronous
mediator. The placement decision doesn't change with async; only the mechanics do.

## Run it

```bash
cd examples/065-validation-sync
uv sync
uv run pytest
```

```text
8 passed
```

Those eight tests drive two endpoints and prove, for each, that a bad **shape** is rejected
at the edge, a valid shape with a broken **invariant** is rejected in the core, and the happy
path works — plus that the core imports no Pydantic.

## The rule: shape at the edge, invariants in the core

**Edge (shape).** A Pydantic model rejects malformed JSON with an automatic 422:

```python
class SubscribeBody(BaseModel):          # api.py — the edge
    email: str
    plan: str = "free"

@app.post("/subscriptions", status_code=201)
def subscribe(body: SubscribeBody) -> Subscription:
    return mediator.send(Subscribe(email=body.email, plan=body.plan))
```

**Core (invariant).** The command owns what its data *means*, and imports no web framework:

```python
@dataclass
class Subscribe(Request[Subscription]):  # core.py — no Pydantic, no FastAPI
    email: str
    plan: str = "free"

    def __post_init__(self) -> None:
        errors = []
        if "@" not in self.email:
            errors.append("email must contain '@'")
        if self.plan not in KNOWN_PLANS:
            errors.append(f"plan must be one of {KNOWN_PLANS}, got {self.plan!r}")
        if errors:
            raise ValidationError(errors)     # the edge maps this to 422
```

`"plan": "gold"` is a valid *string* — the edge lets it through. The *core* knows we don't
sell a "gold" plan, and rejects it. (Only the API import and `async`/`await` differ from the
async twin.)

## Collapsed vs. split: choosing one type or two

- **Collapsed** — when the wire shape equals the domain shape, map field-for-field:
  `SubscribeBody` → `Subscribe` is a trivial pass-through.
- **Split** — when the wire shape *isn't* the domain shape, keep two types and translate at
  the edge. `OrderBody` (nested `customer_email` + `items`) is mapped into `PlaceOrder`
  (`customer` + a tuple of `OrderLine`), so the core never imports Pydantic.

The rule: **collapse when wire shape == domain shape; split the moment they diverge.**
Richer invariants (like the order rules) live in a `ValidationBehavior` that runs before the
handler and raises the same domain `ValidationError`.

## The files

| File | What it is |
| --- | --- |
| [`src/shop/core.py`](src/shop/core.py) | **Start here.** Commands, invariants (`__post_init__` and a `ValidationBehavior`), handlers — no Pydantic, no FastAPI. |
| [`src/shop/api.py`](src/shop/api.py) | The edge: Pydantic DTOs, the collapsed and split mappings, `ValidationError` → 422. |
| [`tests/test_validation.py`](tests/test_validation.py) | Edge-vs-core rejection for both endpoints, and a check that the core imports no Pydantic: `uv run pytest` → `8 passed`. |

## Where next

- [065-validation](../065-validation/) — the async original.
- [070-error-handling](../070-error-handling/) — domain errors vs. framework errors.
- The docs: [requests & responses](https://pymediate.sina-al.uk/docs/guide/requests-responses).
