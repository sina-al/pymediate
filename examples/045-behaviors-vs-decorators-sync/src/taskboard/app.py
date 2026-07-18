"""Run the decorator and behavior versions with strict and permissive limiters."""

from taskboard import behavior, decorator
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, CallCountLimiter, RateLimitExceededError


def main() -> None:
    """Show where each approach is configured and when it runs."""
    print("== decorator: limiter injected into each handler ==")
    decorated = decorator.AddTaskHandler(TaskStore(), CallCountLimiter(limit=2))
    decorated(decorator.AddTask(title="one"))
    decorated(decorator.AddTask(title="two"))
    try:
        decorated(decorator.AddTask(title="three"))
    except RateLimitExceededError as exc:
        print(f"blocked on a direct call: {exc}")

    permissive_decorated = decorator.AddTaskHandler(TaskStore(), AlwaysAllow())
    for i in range(5):
        permissive_decorated(decorator.AddTask(title=f"bulk-{i}"))
    print("a second handler accepted 5 tasks with its own limiter")

    print()
    print("== behavior: limiter configured when the mediator is built ==")
    mediated = behavior.build_mediator(limiter=CallCountLimiter(limit=2))
    mediated.send(behavior.AddTask(title="one"))
    mediated.send(behavior.AddTask(title="two"))
    try:
        mediated.send(behavior.AddTask(title="three"))
    except RateLimitExceededError as exc:
        print(f"blocked during mediator dispatch: {exc}")

    permissive_mediator = behavior.build_mediator(limiter=AlwaysAllow())
    for i in range(5):
        permissive_mediator.send(behavior.AddTask(title=f"bulk-{i}"))
    print("a second mediator accepted 5 tasks with its configured behavior")


if __name__ == "__main__":
    main()
