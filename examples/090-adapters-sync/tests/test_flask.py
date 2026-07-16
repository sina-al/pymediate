"""Tests for the Flask adapter — exercises the whole core through Flask's test client."""

import pytest
from flask.testing import FlaskClient

from taskboard.adapters.flask import create_app


@pytest.fixture
def client() -> FlaskClient:
    app = create_app()
    app.testing = True
    return app.test_client()


def test_add_task_returns_201_with_created_task(client: FlaskClient) -> None:
    response = client.post("/tasks", json={"title": "Buy groceries"})

    assert response.status_code == 201
    assert response.get_json() == {"task_id": 1, "title": "Buy groceries", "done": False}


def test_ids_increment(client: FlaskClient) -> None:
    first = client.post("/tasks", json={"title": "first"}).get_json()
    second = client.post("/tasks", json={"title": "second"}).get_json()

    assert (first["task_id"], second["task_id"]) == (1, 2)


def test_complete_task_marks_done(client: FlaskClient) -> None:
    task = client.post("/tasks", json={"title": "Ship it"}).get_json()

    response = client.post(f"/tasks/{task['task_id']}/complete")

    assert response.status_code == 200
    assert response.get_json()["done"] is True


def test_complete_unknown_task_returns_404(client: FlaskClient) -> None:
    response = client.post("/tasks/999/complete")

    assert response.status_code == 404
    assert response.get_json() == {"error": "No task with id 999"}


def test_list_open_tasks_excludes_done(client: FlaskClient) -> None:
    keep = client.post("/tasks", json={"title": "keep me"}).get_json()
    done = client.post("/tasks", json={"title": "finish me"}).get_json()
    client.post(f"/tasks/{done['task_id']}/complete")

    open_tasks = client.get("/tasks").get_json()

    assert [task["task_id"] for task in open_tasks] == [keep["task_id"]]


def test_each_app_gets_its_own_store(client: FlaskClient) -> None:
    client.post("/tasks", json={"title": "mine"})

    other_client = create_app().test_client()

    assert other_client.get("/tasks").get_json() == []
