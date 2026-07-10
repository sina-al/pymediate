"""FastAPI adapter: the same routes as the Flask adapter, on a different framework.

Endpoints are plain ``def`` functions (FastAPI runs them in a threadpool) because the
core is synchronous — the async mirror of this example (`examples/adapters-aio/`) has
the ``async def`` version. The core's Task dataclass doubles as the response model,
and TaskNotFoundError maps to HTTP 404 via FastAPI's exception_handler hook.
"""

from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from taskboard.core import (
    AddTask,
    CompleteTask,
    ListOpenTasks,
    Task,
    TaskNotFoundError,
    build_mediator,
)


class NewTask(BaseModel):
    """Request body for creating a task."""

    title: str


def create_app() -> FastAPI:
    """Build a FastAPI app around a fresh mediator (and therefore a fresh store)."""
    app = FastAPI(title="Task board")
    mediator = build_mediator()

    @app.exception_handler(TaskNotFoundError)
    def task_not_found(request: HTTPRequest, error: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(error)})

    @app.post("/tasks", status_code=201)
    def add_task(new_task: NewTask) -> Task:
        return mediator.send(AddTask(title=new_task.title))

    @app.post("/tasks/{task_id}/complete")
    def complete_task(task_id: int) -> Task:
        return mediator.send(CompleteTask(task_id=task_id))

    @app.get("/tasks")
    def list_open_tasks() -> list[Task]:
        return mediator.send(ListOpenTasks())

    return app


app = create_app()
