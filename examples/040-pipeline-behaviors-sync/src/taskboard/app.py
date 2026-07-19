"""Wire the pipeline and run a short demo.

``build_mediator`` registers four behaviors before the handlers. Registration order is
execution order, and each behavior's type parameter selects the requests it receives.
Commands pass through logging, authorization, and a transaction-boundary trace. Queries
pass through logging and caching.
"""

from pymediate.sync import Mediator, Services

from .behaviors import (
    AuthorizationBehavior,
    CachingBehavior,
    LoggingBehavior,
    TransactionBehavior,
)
from .domain import (
    AddTask,
    AddTaskHandler,
    CompleteTaskHandler,
    FakeCache,
    GetTask,
    GetTaskHandler,
    ListOpenTasksHandler,
    Principal,
    TaskStore,
)


def build_mediator(
    *,
    store: TaskStore | None = None,
    cache: FakeCache | None = None,
    trace: list[str] | None = None,
    principal: Principal | None = None,
) -> Mediator:
    """Wire a mediator whose behaviors= list declares the pipeline outermost-first.

    Args:
        store: Task storage; a fresh empty store when omitted.
        cache: Read cache; a fresh empty cache when omitted.
        trace: Shared list the behaviors append their markers to; a new list when omitted.
        principal: The user commands run as; a write-allowed ``system`` user when omitted.

    Returns:
        A mediator wired with the four behaviors and the four handlers.
    """
    store = store if store is not None else TaskStore()
    cache = cache if cache is not None else FakeCache()
    trace = trace if trace is not None else []
    principal = principal if principal is not None else Principal("system", can_write=True)

    services = Services()
    services.add(LoggingBehavior(trace))
    services.add(AuthorizationBehavior(principal, trace))
    services.add(CachingBehavior(cache, trace))
    services.add(TransactionBehavior(trace))
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    services.add(GetTaskHandler(store))
    services.add(ListOpenTasksHandler(store))
    return Mediator(
        services.provider(),
        behaviors=[
            LoggingBehavior,  # 1. outermost — every request
            AuthorizationBehavior,  # 2. commands only
            CachingBehavior,  # 3. queries only; may short-circuit
            TransactionBehavior,  # 4. innermost — commands only
        ],
    )


def main() -> None:
    """Run a short demo showing the stack ordering and a cache short-circuit."""
    store = TaskStore()
    trace: list[str] = []
    mediator = build_mediator(store=store, trace=trace)

    task = mediator.send(AddTask(title="Buy groceries"))
    print(f"Created {task.title!r} (id={task.task_id})")

    # Same query twice: the first read runs the handler, the second is a cache hit.
    mediator.send(GetTask(task_id=task.task_id))
    mediator.send(GetTask(task_id=task.task_id))
    print(f"GetTask handler ran {store.reads} time(s) across 2 sends (cache served the rest)")

    print("Pipeline trace:")
    for entry in trace:
        print(f"  {entry}")


if __name__ == "__main__":
    main()
