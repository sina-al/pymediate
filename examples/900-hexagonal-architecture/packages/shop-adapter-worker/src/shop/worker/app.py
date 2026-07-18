"""Command-line entry point for outbox relay and broker consumer roles."""

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from shop.application.container import ApplicationContainer
from shop.bindings.loading import create_application_container, load_wiring
from shop.bindings.wiring import Wiring
from shop.worker.container import ConsumerContainer, RelayContainer

logger = logging.getLogger(__name__)


def create_relay_container(wiring: Wiring) -> RelayContainer:
    """Compose the relay without constructing the application graph."""
    expected = set(RelayContainer.dependencies)
    relay = wiring.role("relay", expected)
    container = RelayContainer(**relay.providers)
    container.check_dependencies()
    return container


def create_consumer_container(
    wiring: Wiring, application: ApplicationContainer
) -> ConsumerContainer:
    """Compose broker consumption around the shared application mediator."""
    expected = set(ConsumerContainer.dependencies) - {"mediator"}
    consumer = wiring.role("consumer", expected)
    container = ConsumerContainer(mediator=application.mediator, **consumer.providers)
    container.check_dependencies()
    return container


async def run_relay_once(container: RelayContainer) -> int:
    """Publish one leased outbox batch."""
    return await container.relay().run_once()


async def run_consumer_once(container: ConsumerContainer) -> bool:
    """Dispatch one locked broker message through the mediator."""
    return await container.consumer().run_once()


async def _run_forever(operation: Callable[[], Awaitable[Any]], poll_interval: float) -> None:
    while True:
        result = await operation()
        if not result:
            await asyncio.sleep(poll_interval)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relay and consume durable shop messages")
    subparsers = parser.add_subparsers(dest="role", required=True)
    for role in ("relay", "consume"):
        command = subparsers.add_parser(role)
        command.add_argument("--once", action="store_true")
        command.add_argument("--poll-interval", type=float, default=1.0)
    return parser


async def _run(role: str, once: bool, poll_interval: float) -> None:
    wiring = load_wiring()
    if role == "relay":
        async with wiring.activate("relay"):
            relay = create_relay_container(wiring)
            operation = relay.relay().run_once
            label = "messages published"
            if once:
                print(f"{await operation()} {label}")
                return
            await _run_forever(operation, poll_interval)
        return

    async with wiring.activate("application", "consumer"):
        application = create_application_container(wiring)
        consumer = create_consumer_container(wiring, application)
        operation = consumer.consumer().run_once
        label = "message consumed"
        if once:
            print(f"{await operation()} {label}")
            return
        await _run_forever(operation, poll_interval)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected independently deployable worker role."""
    logging.basicConfig(level=logging.INFO)
    args = _parser().parse_args(argv)
    try:
        asyncio.run(_run(args.role, args.once, args.poll_interval))
    except KeyboardInterrupt:
        logger.info("worker stopped")
