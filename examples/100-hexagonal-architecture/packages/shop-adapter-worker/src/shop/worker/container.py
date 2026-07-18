"""Dependency Injector graphs owned by the worker adapter."""

from dependency_injector import containers, providers
from opentelemetry import trace
from pymediate import Mediator

from shop.ports.broker import MessageConsumer, MessagePublisher
from shop.ports.inbox import MessageInbox
from shop.ports.outbox import OutboxRelaySource
from shop.worker.consumer import MediatorMessageConsumer
from shop.worker.registry import decode_message
from shop.worker.relay import OutboxRelay


class RelayContainer(containers.DeclarativeContainer):
    """Compose only the dependencies needed by the outbox relay process."""

    outbox = providers.Dependency(instance_of=OutboxRelaySource)
    publisher = providers.Dependency(instance_of=MessagePublisher)

    relay = providers.Factory(OutboxRelay, outbox=outbox, publisher=publisher)


class ConsumerContainer(containers.DeclarativeContainer):
    """Compose broker consumption around the shared application mediator."""

    mediator = providers.Dependency(instance_of=Mediator)
    queue = providers.Dependency(instance_of=MessageConsumer)
    inbox = providers.Dependency(instance_of=MessageInbox)
    tracer = providers.Singleton(trace.get_tracer, "shop.worker")

    consumer = providers.Factory(
        MediatorMessageConsumer,
        queue=queue,
        inbox=inbox,
        mediator=mediator,
        decoder=providers.Object(decode_message),
        tracer=tracer,
    )
