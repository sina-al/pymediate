"""Publish one event to several handlers with PyMediate's synchronous API.

``send`` asks one handler a question and returns its answer. ``publish`` reports that
something happened and lets any number of event handlers react. Completing a task publishes
one ``TaskCompleted`` event to a notifier, statistics counter, and audit log. The synchronous
mediator runs them sequentially in registration order. Publishing an event with no matching
handlers also succeeds. The asynchronous mirror is 020-events.
"""

from dataclasses import dataclass, field

from pymediate.sync import Event, EventHandler, Mediator, Services

# ---- Events: past-tense facts, broadcast to whoever cares ----


@dataclass
class TaskCompleted(Event):
    """Announces that a task was finished; delivered to every subscriber."""

    task_id: int
    title: str


@dataclass
class TaskArchived(Event):
    """Announces that a task was archived. Nothing subscribes to it — yet."""

    task_id: int


# ---- Shared activity feed the demo watches ----


@dataclass
class Dashboard:
    """What the subscribers write to; each one touches only its own concern.

    ``feed`` records a ``started``/``done`` marker around every reaction, in the order the
    reactions actually run — which is what makes sequential delivery visible: under sync
    ``publish`` each subscriber finishes before the next one starts.
    """

    feed: list[str] = field(default_factory=list)
    completed: int = 0


# ---- Subscribers: any number may react to one event, none aware of the others ----


class Notifier(EventHandler[TaskCompleted]):
    """Tells the user their task is done."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("notify  started")
        self._dashboard.feed.append(f"notify  done    (queued task completion for {event.title})")


class StatsCounter(EventHandler[TaskCompleted]):
    """Counts completions for a dashboard tile."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("stats   started")
        self._dashboard.completed += 1
        total = self._dashboard.completed
        self._dashboard.feed.append(f"stats   done    (completions now {total})")


class AuditLog(EventHandler[TaskCompleted]):
    """Records every completion in an append-only audit trail."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("audit   started")
        self._dashboard.feed.append(f"audit   done    (task {event.task_id} logged)")


def build_mediator(dashboard: Dashboard | None = None) -> Mediator:
    """Wire a mediator: three subscribers for TaskCompleted, none for TaskArchived."""
    dashboard = dashboard if dashboard is not None else Dashboard()

    services = Services()
    # Registration order is delivery order: the sync mediator runs each subscriber to
    # completion before starting the next, so each started/done pair stays together.
    services.add(Notifier(dashboard))
    services.add(StatsCounter(dashboard))
    services.add(AuditLog(dashboard))
    return Mediator(services.provider())


def main() -> None:
    """Publish one event to three sequential subscribers, then one to nobody."""
    dashboard = Dashboard()
    mediator = build_mediator(dashboard)

    print("Completing task 1: 'Buy groceries'")
    mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
    for line in dashboard.feed:
        print(f"  {line}")
    print("Each event handler finished before the next started; ", end="")
    print("synchronous publish was sequential.\n")

    print("Archiving task 1 (no handlers registered for TaskArchived):")
    mediator.publish(TaskArchived(task_id=1))
    print("  publish returned; no matching handlers ran.")


if __name__ == "__main__":
    main()
