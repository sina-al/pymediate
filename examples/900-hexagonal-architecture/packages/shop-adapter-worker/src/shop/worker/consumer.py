"""Consume broker deliveries and translate them into mediator dispatches."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from opentelemetry import context, propagate
from opentelemetry.trace import SpanKind, Tracer
from pymediate import Mediator, Request

from shop.ports.broker import MessageConsumer, MessageDelivery
from shop.ports.inbox import InboxDisposition, MessageInbox
from shop.ports.integration import IntegrationMessage
from shop.ports.leases import LeaseToken

type MessageDecoder = Callable[[IntegrationMessage], Request[Any]]

logger = logging.getLogger(__name__)


class InboxLeaseLostError(RuntimeError):
    """Raised when a consumer no longer owns the inbox processing claim."""


class MediatorMessageConsumer:
    """Dispatch one locked broker delivery with inbox-based deduplication."""

    def __init__(
        self,
        queue: MessageConsumer,
        inbox: MessageInbox,
        mediator: Mediator,
        decoder: MessageDecoder,
        tracer: Tracer,
        inbox_lease_seconds: int = 120,
        renew_interval_seconds: float = 30,
    ) -> None:
        self._queue = queue
        self._inbox = inbox
        self._mediator = mediator
        self._decoder = decoder
        self._tracer = tracer
        self._inbox_lease_seconds = inbox_lease_seconds
        self._renew_interval_seconds = renew_interval_seconds

    async def run_once(self) -> bool:
        """Receive and settle one message, returning whether a delivery existed."""
        delivery = await self._queue.receive()
        if delivery is None:
            return False

        try:
            message = delivery.message
        except BaseException:
            await self._abandon_without_masking(delivery)
            raise

        try:
            claim = await self._inbox.claim_inbox_message(
                message.message_id, self._inbox_lease_seconds
            )
        except BaseException:
            await self._abandon_without_masking(delivery)
            raise

        if claim.disposition is InboxDisposition.PROCESSED:
            await delivery.complete()
            return True
        if claim.disposition is InboxDisposition.BUSY:
            await delivery.abandon()
            return True

        lease_token = claim.lease_token
        assert lease_token is not None
        inbox_completed = False
        context_token: object | None = None

        async def dispatch() -> None:
            nonlocal inbox_completed
            with self._tracer.start_as_current_span(
                "process integration message",
                kind=SpanKind.CONSUMER,
                attributes={
                    "messaging.operation.type": "process",
                    "messaging.message.id": message.message_id,
                    "shop.message.type": message.event_type,
                },
            ):
                request = self._decoder(message)
                await self._mediator.send(request)
                inbox_completed = await self._inbox.complete_inbox_message(
                    message.message_id, lease_token
                )
                if not inbox_completed:
                    raise InboxLeaseLostError(f"inbox lease lost for message {message.message_id}")

        try:
            parent = propagate.extract(delivery.trace_context)
            context_token = context.attach(parent)
            await self._run_with_renewal(delivery, message.message_id, lease_token, dispatch)
        except BaseException:
            if not inbox_completed:
                await self._release_without_masking(message.message_id, lease_token)
                await self._abandon_without_masking(delivery)
            raise
        finally:
            if context_token is not None:
                context.detach(context_token)

        # Inbox completion precedes broker completion. If this call fails,
        # redelivery observes the processed inbox row and completes without redispatch.
        await delivery.complete()
        return True

    async def _run_with_renewal(
        self,
        delivery: MessageDelivery,
        message_id: str,
        lease_token: LeaseToken,
        operation: Callable[[], Awaitable[None]],
    ) -> None:
        stopped = asyncio.Event()
        processing = asyncio.ensure_future(operation())
        renewal = asyncio.create_task(
            self._renew_until_stopped(delivery, message_id, lease_token, stopped)
        )
        try:
            done, _ = await asyncio.wait({processing, renewal}, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            processing.cancel()
            renewal.cancel()
            await asyncio.gather(processing, renewal, return_exceptions=True)
            raise
        if renewal in done:
            renewal_error = renewal.exception()
            if renewal_error is not None:
                processing.cancel()
                with suppress(asyncio.CancelledError):
                    await processing
                raise renewal_error

        failure: BaseException | None = None
        try:
            await processing
        except BaseException as exc:
            failure = exc
        finally:
            stopped.set()
            try:
                await renewal
            except BaseException as exc:
                if failure is None:
                    failure = exc
                else:
                    logger.exception(
                        "message-lock renewal failed while processing also failed",
                        exc_info=exc,
                        extra={"message_id": message_id},
                    )
        if failure is not None:
            raise failure

    async def _renew_until_stopped(
        self,
        delivery: MessageDelivery,
        message_id: str,
        lease_token: LeaseToken,
        stopped: asyncio.Event,
    ) -> None:
        while True:
            try:
                await asyncio.wait_for(stopped.wait(), timeout=self._renew_interval_seconds)
                return
            except TimeoutError:
                await delivery.renew()
                renewed = await self._inbox.renew_inbox_message(
                    message_id, lease_token, self._inbox_lease_seconds
                )
                if not renewed:
                    raise InboxLeaseLostError(
                        f"inbox lease lost for message {message_id}"
                    ) from None

    async def _release_without_masking(self, message_id: str, lease_token: LeaseToken) -> None:
        try:
            await self._inbox.release_inbox_message(message_id, lease_token)
        except Exception:
            logger.exception("failed to release inbox lease", extra={"message_id": message_id})

    @staticmethod
    async def _abandon_without_masking(delivery: MessageDelivery) -> None:
        try:
            await delivery.abandon()
        except Exception:
            logger.exception("failed to abandon broker delivery")
