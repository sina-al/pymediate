"""aiohttp adapter: the same routes on aiohttp's server.

aiohttp has no Pydantic and no decorator-per-exception hook, so this adapter shows a
third dialect of the same translation: plain handler functions pulling the mediator
out of the application (typed via ``web.AppKey``), and a middleware mapping
``TaskNotFoundError`` to HTTP 404.
"""

from dataclasses import asdict

from aiohttp import web
from aiohttp.typedefs import Handler
from pymediate import Mediator

from taskboard.domain import TaskNotFoundError
from taskboard.messages import AddTask, CompleteTask, ListOpenTasks
from taskboard.wiring import build_mediator

MEDIATOR = web.AppKey("mediator", Mediator)


@web.middleware
async def task_not_found_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Translate the core's TaskNotFoundError into a 404 for every route."""
    try:
        return await handler(request)
    except TaskNotFoundError as error:
        return web.json_response({"error": str(error)}, status=404)


async def add_task(request: web.Request) -> web.Response:
    payload = await request.json()
    task = await request.app[MEDIATOR].send(AddTask(title=payload["title"]))
    return web.json_response(asdict(task), status=201)


async def complete_task(request: web.Request) -> web.Response:
    task_id = int(request.match_info["task_id"])
    task = await request.app[MEDIATOR].send(CompleteTask(task_id=task_id))
    return web.json_response(asdict(task))


async def list_open_tasks(request: web.Request) -> web.Response:
    tasks = await request.app[MEDIATOR].send(ListOpenTasks())
    return web.json_response([asdict(task) for task in tasks])


def create_app() -> web.Application:
    """Build an aiohttp app around a fresh mediator (and therefore a fresh store)."""
    app = web.Application(middlewares=[task_not_found_middleware])
    app[MEDIATOR] = build_mediator()
    app.router.add_post("/tasks", add_task)
    app.router.add_post("/tasks/{task_id}/complete", complete_task)
    app.router.add_get("/tasks", list_open_tasks)
    return app


if __name__ == "__main__":
    web.run_app(create_app())
