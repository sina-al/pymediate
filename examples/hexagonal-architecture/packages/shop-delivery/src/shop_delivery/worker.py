"""The worker doorway: the same requests, sent from outside the request cycle.

The article's ticket, resolved: the export that used to time out in a web request is
the same ``ExportOrders`` message, dispatched here instead. The worker knows the
mediator and the shape of a job — nothing else.
"""

import json
import logging
import queue
from typing import Any

import redis
from pymediate import Mediator
from redis.exceptions import TimeoutError as RedisTimeoutError

from shop_core.orders import ExportOrders, ExportResult

logger = logging.getLogger("shop.worker")

EXPORT_QUEUE = "shop:exports"


class RedisJobQueue:
    """JobQueue on a Redis list — jobs cross process boundaries."""

    def __init__(self, client: redis.Redis, queue_name: str = EXPORT_QUEUE) -> None:
        self._client = client
        self._queue_name = queue_name

    def enqueue(self, job: dict[str, Any]) -> None:
        self._client.rpush(self._queue_name, json.dumps(job))


def handle_job(mediator: Mediator, job: dict[str, Any]) -> ExportResult:
    """Turn one queued job back into a request and send it — the whole worker, really."""
    result = mediator.send(ExportOrders(customer_id=job["customer_id"], fmt=job.get("fmt", "csv")))
    logger.info("export ready: %s (%s rows)", result.url, result.rows)
    return result


def run_redis_worker(
    mediator: Mediator, client: redis.Redis, queue_name: str = EXPORT_QUEUE
) -> None:
    """Consume export jobs from Redis forever (the postgres/neo4j variants)."""
    logger.info("worker consuming %r", queue_name)
    while True:
        try:
            message = client.blpop([queue_name], timeout=5)
        except RedisTimeoutError:
            # The blocking pop outlived the client's socket timeout — an idle tick,
            # not a failure. Poll again.
            continue
        if message is None:
            continue
        _, payload = message
        handle_job(mediator, json.loads(payload))


def drain_memory_queue(mediator: Mediator, jobs: "queue.Queue[dict[str, Any]]") -> None:
    """Consume export jobs from an in-process queue forever (the memory variant).

    Runs as a daemon thread inside the web process, because in-memory persistence
    only exists in that one process — a separate worker container would export from
    an empty store.
    """
    while True:
        handle_job(mediator, jobs.get())
