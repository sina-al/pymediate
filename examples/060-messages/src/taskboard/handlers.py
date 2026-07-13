"""Handlers for the three requests — deliberately thin, because the messages did the work.

Note what's *absent*: no handler re-checks the title, the tag, the page, or the secret.
That validation already ran in each request's ``__post_init__``, at construction, so by the
time a handler is called the request is known-good. The handlers just do the operation.
"""

from pymediate import RequestHandler

from .domain import Task, TaskStore, Webhook
from .messages import CreateTask, RegisterWebhook, SearchByTag


class CreateTaskHandler(RequestHandler[CreateTask]):
    """Persist a validated CreateTask — no re-validation needed."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: CreateTask) -> Task:
        return self._store.add(request.title, request.tags, request.priority)


class SearchByTagHandler(RequestHandler[SearchByTag]):
    """Answer a SearchByTag, caching by the *request itself* — which is a frozen value.

    The cache is keyed on the ``SearchByTag`` instance. Two searches with equal fields are
    equal and hash equal (that's what ``frozen=True`` buys), so the second call is a hit and
    the store is never touched again. ``hits`` lets the demo and tests observe it.
    """

    def __init__(self, store: TaskStore) -> None:
        self._store = store
        self._cache: dict[SearchByTag, list[Task]] = {}
        self.hits = 0

    async def __call__(self, request: SearchByTag) -> list[Task]:
        cached = self._cache.get(request)
        if cached is not None:
            self.hits += 1
            return cached
        start = (request.page - 1) * request.per_page
        results = self._store.with_tag(request.tag)[start : start + request.per_page]
        self._cache[request] = results
        return results


class RegisterWebhookHandler(RequestHandler[RegisterWebhook]):
    """Register a webhook — the secret arrives already length-checked."""

    def __init__(self) -> None:
        self._next_id = 1

    async def __call__(self, request: RegisterWebhook) -> Webhook:
        webhook = Webhook(webhook_id=self._next_id, url=request.url)
        self._next_id += 1
        return webhook
