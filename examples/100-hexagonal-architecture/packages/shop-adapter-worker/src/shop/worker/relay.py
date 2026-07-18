"""Relay committed transactional-outbox messages into a broker."""

import asyncio
import logging

from shop.ports.broker import MessagePublisher
from shop.ports.outbox import OutboxClaim, OutboxRelaySource

logger = logging.getLogger(__name__)


class OutboxLeaseLostError(RuntimeError):
    """Raised when a relay no longer owns the message it tried to settle."""


class OutboxRelay:
    """Lease and publish one bounded batch of committed integration messages."""

    def __init__(
        self,
        outbox: OutboxRelaySource,
        publisher: MessagePublisher,
        batch_size: int = 20,
        lease_seconds: int = 120,
        renew_interval_seconds: float = 30,
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds
        self._renew_interval_seconds = renew_interval_seconds

    async def run_once(self) -> int:
        """Publish one batch and return the number confirmed by the broker."""
        claims = await self._outbox.claim_outbox_messages(self._batch_size, self._lease_seconds)
        if not claims:
            return 0

        active = {claim.message_id: claim for claim in claims}
        active_lock = asyncio.Lock()
        stopped = asyncio.Event()
        renewal_failure: BaseException | None = None

        async def renew_claims() -> None:
            nonlocal renewal_failure
            try:
                while True:
                    try:
                        await asyncio.wait_for(stopped.wait(), timeout=self._renew_interval_seconds)
                        return
                    except TimeoutError:
                        async with active_lock:
                            for claim in active.values():
                                renewed = await self._outbox.renew_outbox_message(
                                    claim.message_id,
                                    claim.lease_token,
                                    self._lease_seconds,
                                )
                                if not renewed:
                                    raise OutboxLeaseLostError(
                                        f"outbox lease lost for message {claim.message_id}"
                                    ) from None
            except BaseException as exc:
                renewal_failure = exc
                raise

        renewal = asyncio.create_task(renew_claims())
        published = 0
        failure: BaseException | None = None
        try:
            for claim in claims:
                await self._publisher.publish(claim.message)
                async with active_lock:
                    if renewal_failure is not None:
                        raise renewal_failure
                    settled = await self._outbox.mark_outbox_message_published(
                        claim.message_id, claim.lease_token
                    )
                    if not settled:
                        raise OutboxLeaseLostError(
                            f"outbox lease lost for message {claim.message_id}"
                        )
                    del active[claim.message_id]
                published += 1
        except BaseException as exc:
            failure = exc
        finally:
            stopped.set()
            try:
                await renewal
            except BaseException as exc:
                if failure is None:
                    failure = exc
            await self._release_claims(tuple(active.values()), failure)

        if failure is not None:
            raise failure
        return published

    async def _release_claims(
        self, claims: tuple[OutboxClaim, ...], failure: BaseException | None
    ) -> None:
        for claim in claims:
            try:
                await self._outbox.release_outbox_message(claim.message_id, claim.lease_token)
            except Exception:
                logger.exception(
                    "failed to release outbox lease",
                    extra={
                        "message_id": claim.message_id,
                        "original_failure": repr(failure),
                    },
                )
