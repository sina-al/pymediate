# Best practices

Each guide page ends with a best-practices section scoped to its own topic. This page indexes those, and adds a few cross-cutting practices that don't belong to any single topic.

## Topic-specific best practices

- [Requests and responses](../guide/requests-responses.md#best-practices) - Keep requests simple, use type hints, namespace by feature.
- [Handlers](../guide/handlers.md#best-practices) - Single responsibility, dependency injection, stateless by default.
- [Mediator](../guide/mediator.md#best-practices) - One mediator instance per application, don't mix mediator and direct handler calls.
- [Pipeline behaviors](../guide/pipeline-behaviors.md#best-practices) - Keep behaviors focused and reusable, always call `next()` unless short-circuiting is intentional, mind registration order.
- [Dataclasses](../guide/dataclasses.md#best-practices) - `frozen=True` for requests, `default_factory` for mutable defaults, validate in `__post_init__`.
- [Error handling](../guide/error-handling.md) - Keeping domain errors independent of the framework, and mapping them at the edge.

## Project structure

Organize by business capability, not by technical layer — keep a feature's requests, handlers, and tests together rather than splitting them into parallel `requests/`, `handlers/`, `tests/` trees.

```
app/
    orders/
        requests.py
        handlers.py
        test_handlers.py
    users/
        requests.py
        handlers.py
        test_handlers.py
    payments/
        requests.py
        handlers.py
        test_handlers.py
```

This mirrors [Requests and responses: namespace by feature](../guide/requests-responses.md#best-practices) and keeps each handler's test file next to the handler it covers, per [Testing](testing.md#fixtures-and-organization).

## Choosing between `Services` and a DI container

Both implement the same `ServiceProvider` protocol, so `Mediator` doesn't care which one you use — the choice is about how you want to manage object lifetimes and wiring, not about PyMediate itself:

- **`Services`** is enough for most applications: it's a few lines of explicit registration with no framework to learn. Reach for it first.
- **`DependencyInjectorServiceProvider`** earns its keep once you have real lifetime management to do — `Singleton` vs. `Factory` vs. `Scoped` providers, or dependencies that themselves need building from configuration. See [Dependency injection](../guide/dependency-injection.md).

Don't reach for a DI container just to avoid writing `services.add(...)` calls — that's not the problem it solves.

## Versioning requests

Once a request type ships, treat its fields as a public contract. Add optional fields with defaults rather than changing existing ones; if a change would break existing callers, introduce a new versioned request type instead and translate at the adapter boundary.

```python
@dataclass
class CreateUserRequestV1(Request[UserCreated]):
    username: str
    email: str

@dataclass
class CreateUserRequestV2(Request[UserCreated]):
    username: str
    email: str
    phone: str | None = None

def translate_v1_to_v2(v1: CreateUserRequestV1) -> CreateUserRequestV2:
    return CreateUserRequestV2(username=v1.username, email=v1.email, phone=None)
```

This keeps the version translation in the adapter, not the handler — the handler only ever sees one shape. See [Requests and responses: request versioning](../guide/requests-responses.md#3-request-versioning) for the fuller pattern.

## Next steps

- [Type safety](type-safety.md) - What mypy checks statically vs. what PyMediate checks at import time.
- [Testing](testing.md) - Testing handlers, the mediator, and pipeline behaviors.
- [Troubleshooting](troubleshooting.md) - Common configuration mistakes and how to fix them.
