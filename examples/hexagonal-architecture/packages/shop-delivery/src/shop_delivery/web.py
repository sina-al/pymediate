"""The web doorway: Flask routes that shrink to intent.

Every route builds a request object and sends it — except the export, which the
article's ticket taught us to keep out of the request cycle: the route enqueues a
job and answers 202, and the worker sends the same request later.
"""

from dataclasses import asdict

from flask import Flask, Response, jsonify, request
from pymediate import Mediator

from shop_core.customers import GetCustomer, RegisterCustomer
from shop_core.errors import (
    CustomerNotFoundError,
    InvalidOrderStateError,
    OrderNotFoundError,
)
from shop_core.orders import CancelOrder, PlaceOrder, RefundOrder
from shop_domain.orders import LineItem
from shop_ports.jobs import JobQueue


def create_app(mediator: Mediator, jobs: JobQueue) -> Flask:
    """Build the Flask app around a finished mediator and a job queue."""
    app = Flask("shop")

    @app.errorhandler(CustomerNotFoundError)
    @app.errorhandler(OrderNotFoundError)
    def not_found(error: Exception) -> tuple[Response, int]:
        return jsonify({"error": str(error)}), 404

    @app.errorhandler(InvalidOrderStateError)
    def conflict(error: InvalidOrderStateError) -> tuple[Response, int]:
        return jsonify({"error": str(error)}), 409

    @app.post("/customers")
    def register_customer() -> tuple[Response, int]:
        payload = request.get_json()
        customer = mediator.send(RegisterCustomer(name=payload["name"], email=payload["email"]))
        return jsonify(asdict(customer)), 201

    @app.get("/customers/<customer_id>")
    def get_customer(customer_id: str) -> Response:
        return jsonify(asdict(mediator.send(GetCustomer(customer_id=customer_id))))

    @app.post("/orders")
    def place_order() -> tuple[Response, int]:
        payload = request.get_json()
        items = [
            LineItem(
                sku=item["sku"],
                quantity=item["quantity"],
                unit_price_cents=item["unit_price_cents"],
            )
            for item in payload["items"]
        ]
        order = mediator.send(PlaceOrder(customer_id=payload["customer_id"], items=items))
        return jsonify(asdict(order)), 201

    @app.post("/orders/<order_id>/cancel")
    def cancel_order(order_id: str) -> Response:
        return jsonify(asdict(mediator.send(CancelOrder(order_id=order_id))))

    @app.post("/orders/<order_id>/refund")
    def refund_order(order_id: str) -> Response:
        payload = request.get_json(silent=True) or {}
        refund = mediator.send(
            RefundOrder(order_id=order_id, to_store_credit=payload.get("to_store_credit", False))
        )
        return jsonify(asdict(refund))

    @app.post("/orders/export")
    def export_orders() -> tuple[Response, int]:
        payload = request.get_json()
        jobs.enqueue({"customer_id": payload["customer_id"], "fmt": payload.get("fmt", "csv")})
        return jsonify({"status": "queued"}), 202

    return app


def serve(app: Flask, port: int = 8000) -> None:
    """Serve the app on waitress (a small production WSGI server)."""
    from waitress import serve as waitress_serve

    waitress_serve(app, host="0.0.0.0", port=port)  # noqa: S104
