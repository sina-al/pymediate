# 065-validation-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F065-validation-sync%2Fdevcontainer.json)

This example separates request-body schema validation from business rules. FastAPI and
Pydantic validate incoming HTTP data; transport-independent commands enforce rules that must
also hold for callers outside HTTP.

## Run

From this directory:

```bash
uv sync
uv run pytest
```

```text
8 passed
```

The tests exercise two synchronous endpoints. Each endpoint rejects invalid input schemas,
rejects a business-rule violation, and accepts valid input. A separate test confirms that the
core does not import Pydantic.

## Validate schemas at the HTTP boundary

Pydantic checks the parsed JSON object for required fields and field types. FastAPI returns
HTTP 422 before constructing a command when that check fails.

```python
class SubscribeBody(BaseModel):
    email: str
    plan: str = "free"

@app.post("/subscriptions", status_code=201)
def subscribe(body: SubscribeBody) -> Subscription:
    command = Subscribe(email=body.email, plan=body.plan)
    return mediator.send(command)
```

Syntactically malformed JSON is a different failure: the HTTP framework rejects it before a
Pydantic body model can be created.

## Enforce business rules in the core

The core knows which plans the shop sells. That rule applies whether a command came from HTTP,
a command-line tool, or another process.

```python
@dataclass
class Subscribe(Request[Subscription]):
    email: str
    plan: str = "free"

    def __post_init__(self) -> None:
        errors = []
        if "@" not in self.email:
            errors.append("email must contain '@'")
        if self.plan not in KNOWN_PLANS:
            errors.append(f"plan must be one of {KNOWN_PLANS}, got {self.plan!r}")
        if errors:
            raise ValidationError(errors)
```

`"gold"` satisfies the request-body field type because it is a string. The core rejects it
because the shop supports only `"free"` and `"pro"`. The HTTP exception handler maps the
domain `ValidationError` to 422.

## Map body models to commands

The boundary always creates a command, even when the fields match. `SubscribeBody` and
`Subscribe` are distinct types with a direct field mapping.

`OrderBody` needs a structural transformation: it uses `customer_email` and a list of nested
items, while `PlaceOrder` uses `customer` and a tuple of `OrderLine` values.

```python
command = PlaceOrder(
    customer=body.customer_email,
    lines=tuple(
        OrderLine(sku=item.sku, quantity=item.quantity)
        for item in body.items
    ),
)
return mediator.send(command)
```

Name the mapping for what it does: direct field copying when structures match, and a
transformation when they do not.

## Read the code

| File | What to read |
| --- | --- |
| [`src/shop/api.py`](src/shop/api.py) | Start here for body models, both mappings, and HTTP error conversion. |
| [`src/shop/core.py`](src/shop/core.py) | Commands, business rules, validation behavior, and handlers. |
| [`tests/test_validation.py`](tests/test_validation.py) | Schema failures, business-rule failures, mappings, and valid requests. |

## Details

This example contains three related mechanisms:

1. Pydantic validates the request-body schema at the HTTP boundary.
2. The endpoint maps the body model to a command.
3. The core enforces business rules, either in `__post_init__` or in a
   `ValidationBehavior` selected for the command type.

`Subscribe` uses `__post_init__` for rules intrinsic to its data. `PlaceOrder` uses a behavior
to run a registered validator during mediator dispatch. Both raise the same domain error; the
choice depends on where the rule can be maintained and reused.

## Where next

- [070-error-handling-sync](../070-error-handling-sync/) maps domain errors for both HTTP and a
  synchronous command-line interface.
- [065-validation](../065-validation/) shows the asynchronous endpoints.
- Read the [requests and responses guide](https://pymediate.sina-al.uk/docs/guide/requests-responses).
