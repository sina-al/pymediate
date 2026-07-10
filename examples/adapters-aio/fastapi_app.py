"""FastAPI adapter: ``async def`` endpoints awaiting the async core.

Compare with `examples/adapters-sync/fastapi_app.py` — same framework, same routes;
the only differences are ``async def`` and ``await mediator.send()``. The core's Task
dataclass doubles as the response model, and TaskNotFoundError maps to HTTP 404 via
FastAPI's exception_handler hook.
"""

from core import AddTask, CompleteTask, ListOpenTasks, Task, TaskNotFoundError, build_mediator
from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class NewTask(BaseModel):
    """Request body for creating a task."""

    title: str


def create_app() -> FastAPI:
    """Build a FastAPI app around a fresh mediator (and therefore a fresh store)."""
    app = FastAPI(title="Task board")
    mediator = build_mediator()

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found(request: HTTPRequest, error: TaskNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": str(error)})

    @app.post("/tasks", status_code=201)
    async def add_task(new_task: NewTask) -> Task:
        return await mediator.send(AddTask(title=new_task.title))

    @app.post("/tasks/{task_id}/complete")
    async def complete_task(task_id: int) -> Task:
        return await mediator.send(CompleteTask(task_id=task_id))

    @app.get("/tasks")
    async def list_open_tasks() -> list[Task]:
        return await mediator.send(ListOpenTasks())

    return app


app = create_app()
