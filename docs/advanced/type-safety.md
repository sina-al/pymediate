# Type safety

PyMediate's type safety comes from two different mechanisms working together, and they don't catch the same mistakes. Knowing which is which helps you understand what mypy will and won't tell you before you run your code.

## Static checking with mypy

`mediator.send()` infers its return type from the request's `Request[ResponseT]` type parameter, so mypy (and your editor) know the exact response type at the call site — no casts, no `Any`.

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, Services

@dataclass
class UserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)

services = Services()
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
reveal_type(response)  # note: Revealed type is "UserResponse"
```

mypy also enforces that a handler's `__call__` accepts the request type declared in `Handler[RequestT]` — get this wrong and mypy reports a Liskov substitution violation, the same way it would for any incompatible method override.

```python
class BadHandler(Handler[CreateUserRequest]):
    def __call__(self, request: SomeOtherRequest) -> UserResponse:
        ...
# error: Argument 1 of "__call__" is incompatible with supertype "Handler";
# supertype defines the argument type as "CreateUserRequest"  [override]
```

## Runtime checking at class-definition time

A handler's **return** type isn't checked by mypy the same way — mismatched return types are a `ResponseTypeMismatchError`, but it's raised by PyMediate's own `__init_subclass__` validation, not caught statically.

```python
class BadHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> WrongResponse:  # mypy: no error here
        return WrongResponse(...)
# ResponseTypeMismatchError: Response type mismatch in BadHandler
# (raised the moment this class is defined, i.e. at import time)
```

This still catches the mistake early — the error fires as soon as the module is imported, before any request is ever sent — just not during a `mypy` run. The same `__init_subclass__` hook also validates that `__call__` exists, has exactly one parameter besides `self`, and is sync or async as expected (`InvalidHandlerSignatureError`), and that a request actually inherits from `Request[ResponseType]` (`InvalidRequestTypeError`). See [Error handling](../guide/error-handling.md) for the full exception hierarchy.

In short: **wrong parameter type → mypy catches it. Wrong return type or malformed signature → PyMediate catches it at import time.** Both happen before a request is ever processed; neither requires a test run to surface.

## Running mypy on your own code

This project itself is checked with `mypy --strict` (see `mypy.ini`), and the same settings work well for application code built on PyMediate.

```ini
[mypy]
python_version = 3.12
disallow_untyped_defs = false
check_untyped_defs = true
warn_return_any = true
```

A few things that keep mypy effective on PyMediate-based code:

- **Always parameterize `Request`.** `class CreateUserRequest(Request):` (no type argument) type-checks, but you lose response-type inference entirely — see [Requests and responses](../guide/requests-responses.md).
- **Prefer dataclasses over hand-written `__init__`.** mypy infers field types directly from dataclass annotations; a hand-rolled `__init__` is just as valid at runtime but gives mypy less to work with. See [Dataclasses with PyMediate](../guide/dataclasses.md).
- **Avoid `Any` in handler signatures.** It silences exactly the override checking described above — a handler typed `def __call__(self, request: Any) -> Any` will never get an LSP violation from mypy, no matter what it actually does.

## How this project tests its own type safety

If you're contributing to PyMediate itself (rather than just using it), `tests/mypy/snippets/` holds small, standalone scripts that pin down the library's type-checking contract: everything under `valid/` must pass `mypy --strict`, everything under `errors/` must fail it. `tests/mypy/test_mypy.py` runs mypy programmatically against each one and asserts the expected outcome. The files in `errors/` are deliberately broken — if you're touching this codebase and see a type error in one, that's the test working, not a bug to fix.

## Next steps

- [Requests and responses](../guide/requests-responses.md) - Why `Request[ResponseT]` is the source of the inference.
- [Error handling](../guide/error-handling.md) - The full runtime validation exception hierarchy.
- [Testing](testing.md) - Testing handlers and mediators directly.
