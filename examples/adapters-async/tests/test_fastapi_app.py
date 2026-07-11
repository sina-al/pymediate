"""Tests for the FastAPI adapter — exercises the whole core over ASGI with httpx2."""

from collections.abc import AsyncIterator

import httpx2
import pytest

from taskboard.adapters.fastapi_app import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_add_task_returns_201_with_created_task(client: httpx2.AsyncClient) -> None:
    response = await client.post("/tasks", json={"title": "Buy groceries"})

    assert response.status_code == 201
    assert response.json() == {"task_id": 1, "title": "Buy groceries", "done": False}


async def test_ids_increment(client: httpx2.AsyncClient) -> None:
    first = (await client.post("/tasks", json={"title": "first"})).json()
    second = (await client.post("/tasks", json={"title": "second"})).json()

    assert (first["task_id"], second["task_id"]) == (1, 2)


async def test_complete_task_marks_done(client: httpx2.AsyncClient) -> None:
    task = (await client.post("/tasks", json={"title": "Ship it"})).json()

    response = await client.post(f"/tasks/{task['task_id']}/complete")

    assert response.status_code == 200
    assert response.json()["done"] is True


async def test_complete_unknown_task_returns_404(client: httpx2.AsyncClient) -> None:
    response = await client.post("/tasks/999/complete")

    assert response.status_code == 404
    assert response.json() == {"error": "No task with id 999"}


async def test_list_open_tasks_excludes_done(client: httpx2.AsyncClient) -> None:
    keep = (await client.post("/tasks", json={"title": "keep me"})).json()
    done = (await client.post("/tasks", json={"title": "finish me"})).json()
    await client.post(f"/tasks/{done['task_id']}/complete")

    open_tasks = (await client.get("/tasks")).json()

    assert [task["task_id"] for task in open_tasks] == [keep["task_id"]]


async def test_each_app_gets_its_own_store(client: httpx2.AsyncClient) -> None:
    await client.post("/tasks", json={"title": "mine"})

    other_transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=other_transport, base_url="http://test") as other:
        assert (await other.get("/tasks")).json() == []
