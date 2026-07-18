"""Requests: each declares the response type it resolves to.

An adapter's whole job is to build one of these and send it — see any file in
``adapters/`` for the translation from a framework's input to one of these types.
"""

from dataclasses import dataclass

from pymediate import Request

from .domain import Task


@dataclass
class AddTask(Request[Task]):
    """Add a task with the given title; responds with the created Task."""

    title: str


@dataclass
class CompleteTask(Request[Task]):
    """Mark a task as done; responds with the updated Task."""

    task_id: int


@dataclass
class ListOpenTasks(Request[list[Task]]):
    """List all tasks not yet done, oldest first."""
