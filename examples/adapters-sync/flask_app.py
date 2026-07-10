"""Flask adapter: routes translate JSON bodies into core requests and back.

Framework-specific concerns live here and only here: URL routing, JSON
(de)serialization, and mapping the core's TaskNotFoundError to HTTP 404 via
Flask's errorhandler hook.
"""

from dataclasses import asdict

from core import AddTask, CompleteTask, ListOpenTasks, TaskNotFoundError, build_mediator
from flask import Flask, Response, jsonify, request


def create_app() -> Flask:
    """Build a Flask app around a fresh mediator (and therefore a fresh store)."""
    app = Flask(__name__)
    mediator = build_mediator()

    @app.errorhandler(TaskNotFoundError)
    def task_not_found(error: TaskNotFoundError) -> tuple[Response, int]:
        return jsonify({"error": str(error)}), 404

    @app.post("/tasks")
    def add_task() -> tuple[Response, int]:
        payload = request.get_json()
        task = mediator.send(AddTask(title=payload["title"]))
        return jsonify(asdict(task)), 201

    @app.post("/tasks/<int:task_id>/complete")
    def complete_task(task_id: int) -> Response:
        task = mediator.send(CompleteTask(task_id=task_id))
        return jsonify(asdict(task))

    @app.get("/tasks")
    def list_open_tasks() -> Response:
        tasks = mediator.send(ListOpenTasks())
        return jsonify([asdict(task) for task in tasks])

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
