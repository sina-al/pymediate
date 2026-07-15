# 065-validation

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F065-validation%2Fdevcontainer.json)

Where does validation go — the adapter's DTO, or the command? Both, and this example draws
the line: **validate the *shape* of untrusted input at the edge** (Pydantic, at the FastAPI
boundary) and **validate *business invariants* in the core** (transport-independent, no
Pydantic). The command is the contract between them. It also shows *when the DTO and the
command are one type* (a trivial pass-through) and *when to split them* (the wire shape isn't
the domain shape).

## Run it

```bash
cd examples/065-validation
uv sync
uv run pytest
```

```text
8 passed
```

Those eight tests drive two endpoints over ASGI and prove, for each, that a bad **shape** is
rejected at the edge, a valid shape with a broken **invariant** is rejected in the core, and
the happy path works — plus that the core imports no Pydantic.

## The rule: shape at the edge, invariants in the core

**Edge (shape).** A Pydantic model rejects malformed JSON — missing fields, wrong types —
with an automatic 422, before anything reaches your domain:

```python
class SubscribeBody(BaseModel):          # api.py — the edge
    email: str
    plan: str = "free"

@app.post("/subscriptions", status_code=201)
async def subscribe(body: SubscribeBody) -> Subscription:
    return await mediator.send(Subscribe(email=body.email, plan=body.plan))
```

**Core (invariant).** The command owns what its data *means* — which plans exist, whether an
order has any lines — and it never imports a web framework:

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

`"plan": "gold"` is a perfectly valid *string* — the edge lets it through. It's the *core*
that knows we don't sell a "gold" plan, and rejects it. Same 422 to the client, different
layer doing the work.

## Collapsed vs. split: choosing one type or two

**Collapsed — use one shape.** When the wire shape equals the domain shape, the DTO maps to
the command field-for-field. `SubscribeBody` → `Subscribe` is a trivial pass-through; there's
no reason to invent two divergent types.

**Split — map between two shapes.** When the wire shape *isn't* the domain shape — different
names, nesting, or you simply want Pydantic out of the core — keep them separate and translate
at the edge:

```python
class OrderBody(BaseModel):              # wire shape: customer_email + nested items
    customer_email: str
    items: list[LineBody]

@app.post("/orders", status_code=201)
async def place_order(body: OrderBody) -> Order:
    command = PlaceOrder(                # domain shape: customer + a tuple of OrderLine
        customer=body.customer_email,
        lines=tuple(OrderLine(sku=i.sku, quantity=i.quantity) for i in body.items),
    )
    return await mediator.send(command)
```

The rule: **collapse when wire shape == domain shape; split the moment they diverge (or you
want the wire library out of your core).**

## Invariants as a behavior

`Subscribe` validates in `__post_init__`, but richer or reusable rules belong in a
**`ValidationBehavior`** — the [MediatR `ValidationBehavior`](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors)
analog. It runs registered validators before the handler and raises the same domain
`ValidationError`:

```python
class ValidationBehavior(PipelineBehavior[Request]):
    async def __call__(self, request, next):
        errors = [e for v in self._validators.get(type(request), []) for e in v(request)]
        if errors:
            raise ValidationError(errors)
        return await next()
```

`PlaceOrder` is validated this way — "at least one line", "quantity between 1 and 100" — with
no validation code in the command itself.

## The files

| File | What it is |
| --- | --- |
| [`src/shop/core.py`](src/shop/core.py) | **Start here.** Commands, invariants (`__post_init__` and a `ValidationBehavior`), handlers — no Pydantic, no FastAPI. |
| [`src/shop/api.py`](src/shop/api.py) | The edge: Pydantic DTOs, the collapsed and split mappings, `ValidationError` → 422. |
| [`tests/test_validation.py`](tests/test_validation.py) | Edge-vs-core rejection for both endpoints, and a check that the core imports no Pydantic: `uv run pytest` → `8 passed`. |

## Small print

- **One revelation: the placement decision.** How to *design* the message itself (frozen,
  slots, secret fields) is [060-messages](../060-messages/); reusable behaviors are
  [040-pipeline-behaviors](../040-pipeline-behaviors/). This example only answers *where
  validation lives*.
- Both a shape failure and an invariant failure return 422 here, deliberately — the client
  shouldn't care which layer caught it. The bodies differ (Pydantic's `detail` vs the core's
  `errors`), so you can still tell them apart in logs.

## Where next

- [065-validation-sync](../065-validation-sync/) — the same placement decision on `pymediate.sync`.
- [070-error-handling](../070-error-handling/) — domain errors vs. framework errors, the next
  layer of the same idea.
- The docs: [requests & responses](https://pymediate.sina-al.uk/docs/guide/requests-responses).
