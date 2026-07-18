"""Handlers: one handler per request type.

This module contains the framework-independent application logic. Adapters call these
handlers through the mediator rather than importing framework concerns here.
"""

from pymediate.sync import RequestHandler

from .domain import Task, TaskNotFoundError, TaskStore
from .messages import AddTask, CompleteTask, ListOpenTasks


class AddTaskHandler(RequestHandler[AddTask]):
    """Creates tasks in the store."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: AddTask) -> Task:
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


class CompleteTaskHandler(RequestHandler[CompleteTask]):
    """Marks existing tasks as done."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: CompleteTask) -> Task:
        task = self._store.tasks.get(request.task_id)
        if task is None:
            raise TaskNotFoundError(f"No task with id {request.task_id}")
        task.done = True
        return task


class ListOpenTasksHandler(RequestHandler[ListOpenTasks]):
    """Lists tasks that are still open."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: ListOpenTasks) -> list[Task]:
        return [task for task in self._store.tasks.values() if not task.done]
