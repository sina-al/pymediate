"""The requests — designed as immutable, validated value objects.

This is the whole point of the example. A request is a plain dataclass, and the small
decisions on it carry real weight:

- ``frozen=True`` makes a request immutable *and hashable*, so it can be a cache key.
- ``slots=True`` trims per-instance memory for high-volume request types.
- ``field(repr=False)`` keeps a secret out of logs and tracebacks.
- ``__post_init__`` normalizes and validates, so a malformed request **raises at
  construction** — before it ever reaches a handler or the mediator.
- a frozen mixin shares fields and their validation across request types.

Where validation *lives architecturally* (edge DTO vs. core command) is a different
question — that's the ``065-validation`` example. Here the focus is the dataclass itself.
"""

from dataclasses import dataclass, field

from pymediate import Request

from .domain import Task, Webhook


@dataclass(frozen=True, slots=True)
class CreateTask(Request[Task]):
    """Create a task — an immutable, validated command.

    ``frozen=True`` means it can't be mutated in flight; ``slots=True`` trims memory.
    ``__post_init__`` normalizes the title and rejects bad data at construction, so a
    handler never sees an invalid ``CreateTask``.
    """

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


@dataclass(frozen=True)
class PaginationMixin:
    """Shared, self-validating pagination fields for any query that needs them.

    Frozen so it can mix into frozen requests (a dataclass can't inherit across the
    frozen/non-frozen line). The fields are keyword-only so a subclass can add its own
    required positional fields without a "non-default argument follows default" clash.
    """

    page: int = field(default=1, kw_only=True)
    per_page: int = field(default=20, kw_only=True)

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")


@dataclass(frozen=True)
class SearchByTag(PaginationMixin, Request[list[Task]]):
    """Find tasks by tag — a frozen query that doubles as its own cache key.

    Because it's frozen (and therefore hashable), two ``SearchByTag`` values with the same
    fields are equal and hash equal, so a handler can use the request itself as a dict key
    (see ``handlers.SearchByTagHandler``). It reuses ``PaginationMixin`` for ``page`` /
    ``per_page`` and their validation.
    """

    tag: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tag", self.tag.strip().lower())
        if not self.tag:
            raise ValueError("tag cannot be empty")
        super().__post_init__()  # run the mixin's pagination validation too


@dataclass(frozen=True)
class RegisterWebhook(Request[Webhook]):
    """Register a webhook — carries a secret kept out of logs.

    ``field(repr=False)`` drops ``secret`` from the generated ``__repr__``, so printing or
    logging the request (or seeing it in a traceback) never leaks the signing secret.
    """

    url: str
    secret: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("url must be http(s)")
        if len(self.secret) < 8:
            raise ValueError("secret must be at least 8 characters")
