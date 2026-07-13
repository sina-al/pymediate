"""Wire the mediator and run a demo that shows each message-design choice paying off.

This is the synchronous mirror of ``examples/060-messages/app.py`` — same demo, no event
loop. The request dataclasses are identical; only the mediator and handlers are sync.
"""

from dataclasses import FrozenInstanceError

from pymediate.sync import Mediator, Services

from .domain import TaskStore
from .handlers import CreateTaskHandler, RegisterWebhookHandler, SearchByTagHandler
from .messages import CreateTask, RegisterWebhook, SearchByTag


def build_mediator(
    *, store: TaskStore | None = None, search: SearchByTagHandler | None = None
) -> Mediator:
    """Wire a mediator with the three handlers.

    Args:
        store: Task storage; a fresh empty store when omitted.
        search: The search handler; a fresh one over ``store`` when omitted (exposed so a
            caller can observe its ``hits`` counter).

    Returns:
        A mediator wired with the create, search, and webhook handlers.
    """
    store = store if store is not None else TaskStore()
    search = search if search is not None else SearchByTagHandler(store)

    services = Services()
    services.add(CreateTaskHandler(store))
    services.add(search)
    services.add(RegisterWebhookHandler())
    return Mediator(services.provider())


def main() -> None:
    """Show validation-at-construction, a frozen cache key, and a hidden secret."""
    store = TaskStore()
    search = SearchByTagHandler(store)
    mediator = build_mediator(store=store, search=search)

    # 1. A valid request normalizes on the way in (title stripped) and dispatches.
    task = mediator.send(CreateTask(title="  Write the report  ", tags=("work",)))
    print(f"Created task {task.task_id}: title={task.title!r}")

    # 2. A frozen request is immutable — no mutation in flight.
    try:
        task_request = CreateTask(title="immutable")
        task_request.title = "changed"  # type: ignore[misc]
    except FrozenInstanceError:
        print("A frozen request can't be mutated after construction")

    # 3. A bad request fails at *construction* — before any handler or the mediator.
    try:
        CreateTask(title="   ")  # whitespace-only → empty after strip
    except ValueError as exc:
        print(f"Invalid request rejected at construction: {exc}")

    # 4. The frozen request is its own cache key: an identical search is served from cache.
    mediator.send(SearchByTag(tag="work"))
    mediator.send(SearchByTag(tag="WORK"))  # normalizes to "work" → equal → cache hit
    print(f"SearchByTag cache hits across 2 identical searches: {search.hits}")

    # 5. field(repr=False) keeps the secret out of the printed request.
    webhook_request = RegisterWebhook(url="https://example.com/hook", secret="topsecret")
    print(f"Webhook request repr (secret hidden): {webhook_request}")


if __name__ == "__main__":
    main()
