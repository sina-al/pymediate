"""One completion, three reactions: PyMediate's ``publish`` fan-out (async top-level API).

``send`` asks one handler a question and awaits its answer. ``publish`` does the opposite:
it announces that something *happened* and lets any number of subscribers react — no
response, and no idea who is listening. Completing a task here publishes one ``TaskCompleted``
event that three independent subscribers pick up (a notifier, a stats counter, and an audit
log), and the async mediator runs them *concurrently*. A second publish with no subscribers
shows that zero reactions is a perfectly valid outcome. The sync mirror is 020-events-sync.
"""

import asyncio
from dataclasses import dataclass, field

from pymediate import Event, EventHandler, Mediator, Services

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
    reactions actually run — which is what makes concurrent delivery visible: under async
    ``publish`` every subscriber starts before any of them finishes.
    """

    feed: list[str] = field(default_factory=list)
    completed: int = 0


# ---- Subscribers: any number may react to one event, none aware of the others ----


class Notifier(EventHandler[TaskCompleted]):
    """Tells the user their task is done."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    async def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("notify  started")
        await asyncio.sleep(0.03)  # stand-in for an async send (email, push, ...)
        self._dashboard.feed.append(f"notify  done    (queued: Nice work! {event.title} is done.)")


class StatsCounter(EventHandler[TaskCompleted]):
    """Counts completions for a dashboard tile."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    async def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("stats   started")
        await asyncio.sleep(0.02)
        self._dashboard.completed += 1
        total = self._dashboard.completed
        self._dashboard.feed.append(f"stats   done    (completions now {total})")


class AuditLog(EventHandler[TaskCompleted]):
    """Records every completion in an append-only audit trail."""

    def __init__(self, dashboard: Dashboard) -> None:
        self._dashboard = dashboard

    async def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append("audit   started")
        await asyncio.sleep(0.01)
        self._dashboard.feed.append(f"audit   done    (task {event.task_id} logged)")


def build_mediator(dashboard: Dashboard | None = None) -> Mediator:
    """Wire a mediator: three subscribers for TaskCompleted, none for TaskArchived."""
    dashboard = dashboard if dashboard is not None else Dashboard()

    services = Services()
    # Register order is start order. The differing sleeps above mean they finish in a
    # different order — proof the mediator awaited them together, not one after another.
    services.add(Notifier(dashboard))
    services.add(StatsCounter(dashboard))
    services.add(AuditLog(dashboard))
    return Mediator(services.provider())


async def main() -> None:
    """Publish one event to three concurrent subscribers, then one to nobody."""
    dashboard = Dashboard()
    mediator = build_mediator(dashboard)

    print("Completing task 1: 'Buy groceries'")
    await mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
    for line in dashboard.feed:
        print(f"  {line}")
    print("Every subscriber started before any finished — async publish ran them concurrently.\n")

    print("Archiving task 1 (nothing subscribes to TaskArchived):")
    await mediator.publish(TaskArchived(task_id=1))
    print("  publish returned, no handlers ran — zero subscribers is a valid no-op.")


if __name__ == "__main__":
    asyncio.run(main())
