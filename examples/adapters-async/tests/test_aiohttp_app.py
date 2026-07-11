"""Tests for the aiohttp adapter — exercises the whole core through aiohttp's test client."""

from aiohttp.test_utils import TestClient

from taskboard.adapters.aiohttp_app import create_app

# pytest-aiohttp's aiohttp_client fixture starts a real aiohttp test server per test.


async def test_add_task_returns_201_with_created_task(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())

    response = await client.post("/tasks", json={"title": "Buy groceries"})

    assert response.status == 201
    assert await response.json() == {"task_id": 1, "title": "Buy groceries", "done": False}


async def test_ids_increment(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())

    first = await (await client.post("/tasks", json={"title": "first"})).json()
    second = await (await client.post("/tasks", json={"title": "second"})).json()

    assert (first["task_id"], second["task_id"]) == (1, 2)


async def test_complete_task_marks_done(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())
    task = await (await client.post("/tasks", json={"title": "Ship it"})).json()

    response = await client.post(f"/tasks/{task['task_id']}/complete")

    assert response.status == 200
    assert (await response.json())["done"] is True


async def test_complete_unknown_task_returns_404(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())

    response = await client.post("/tasks/999/complete")

    assert response.status == 404
    assert await response.json() == {"error": "No task with id 999"}


async def test_list_open_tasks_excludes_done(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())
    keep = await (await client.post("/tasks", json={"title": "keep me"})).json()
    done = await (await client.post("/tasks", json={"title": "finish me"})).json()
    await client.post(f"/tasks/{done['task_id']}/complete")

    open_tasks = await (await client.get("/tasks")).json()

    assert [task["task_id"] for task in open_tasks] == [keep["task_id"]]


async def test_each_app_gets_its_own_store(aiohttp_client) -> None:
    client: TestClient = await aiohttp_client(create_app())
    await client.post("/tasks", json={"title": "mine"})

    other: TestClient = await aiohttp_client(create_app())

    assert await (await other.get("/tasks")).json() == []
