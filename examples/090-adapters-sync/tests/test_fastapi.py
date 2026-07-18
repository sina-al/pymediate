"""Tests for the FastAPI adapter — exercises the whole core through the TestClient."""

import pytest
from fastapi.testclient import TestClient

from taskboard.adapters.fastapi import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_add_task_returns_201_with_created_task(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "Buy groceries"})

    assert response.status_code == 201
    assert response.json() == {"task_id": 1, "title": "Buy groceries", "done": False}


def test_ids_increment(client: TestClient) -> None:
    first = client.post("/tasks", json={"title": "first"}).json()
    second = client.post("/tasks", json={"title": "second"}).json()

    assert (first["task_id"], second["task_id"]) == (1, 2)


def test_complete_task_marks_done(client: TestClient) -> None:
    task = client.post("/tasks", json={"title": "Ship it"}).json()

    response = client.post(f"/tasks/{task['task_id']}/complete")

    assert response.status_code == 200
    assert response.json()["done"] is True


def test_complete_unknown_task_returns_404(client: TestClient) -> None:
    response = client.post("/tasks/999/complete")

    assert response.status_code == 404
    assert response.json() == {"error": "No task with id 999"}


def test_list_open_tasks_excludes_done(client: TestClient) -> None:
    keep = client.post("/tasks", json={"title": "keep me"}).json()
    done = client.post("/tasks", json={"title": "finish me"}).json()
    client.post(f"/tasks/{done['task_id']}/complete")

    open_tasks = client.get("/tasks").json()

    assert [task["task_id"] for task in open_tasks] == [keep["task_id"]]


def test_each_app_gets_its_own_store(client: TestClient) -> None:
    client.post("/tasks", json={"title": "mine"})

    other_client = TestClient(create_app())

    assert other_client.get("/tasks").json() == []
