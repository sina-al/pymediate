"""Publish one notification to several handlers with PyMediate's synchronous API.

``send`` asks one handler a question and returns its answer. ``publish`` reports that
something happened and lets any number of notification handlers react. Completing a task publishes
one ``TaskCompleted`` notification to a notifier, statistics counter, and audit log. The synchronous
mediator runs them sequentially in registration order. Publishing a notification with no matching
handlers also succeeds. The asynchronous mirror is 020-events.
"""

from dataclasses import dataclass, field

from pymediate.sync import Mediator, Notification, NotificationHandler, Services

# ---- Notifications: past-tense facts, broadcast to whoever cares ----


@dataclass
class TaskCompleted(Notification):
    """Announces that a task was finished; delivered to every subscriber."""

    task_id: int
    title: str


@dataclass
class TaskArchived(Notification):
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


# ---- Subscribers: any number may react to one notification, none aware of the others ----


class Notifier(NotificationHandler[TaskCompleted]):
    """Tells the user their task is done."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, notification: TaskCompleted) -> None:
        self._dashboard.feed.append("notify  started")
        self._dashboard.feed.append(
            f"notify  done    (queued task completion for {notification.title})"
        )


class StatsCounter(NotificationHandler[TaskCompleted]):
    """Counts completions for a dashboard tile."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, notification: TaskCompleted) -> None:
        self._dashboard.feed.append("stats   started")
        self._dashboard.completed += 1
        total = self._dashboard.completed
        self._dashboard.feed.append(f"stats   done    (completions now {total})")


class AuditLog(NotificationHandler[TaskCompleted]):
    """Records every completion in an append-only audit trail."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    def __call__(self, notification: TaskCompleted) -> None:
        self._dashboard.feed.append("audit   started")
        self._dashboard.feed.append(f"audit   done    (task {notification.task_id} logged)")


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
    """Publish one notification to three sequential subscribers, then one to nobody."""
    dashboard = Dashboard()
    mediator = build_mediator(dashboard)

    print("Completing task 1: 'Buy groceries'")
    mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
    for line in dashboard.feed:
        print(f"  {line}")
    print("Each notification handler finished before the next started; ", end="")
    print("synchronous publish was sequential.\n")

    print("Archiving task 1 (no handlers registered for TaskArchived):")
    mediator.publish(TaskArchived(task_id=1))
    print("  publish returned; no matching handlers ran.")


if __name__ == "__main__":
    main()
