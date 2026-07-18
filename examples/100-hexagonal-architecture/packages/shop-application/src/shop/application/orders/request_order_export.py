"""Accept an export by recording durable background work transactionally."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.application.integration_contracts import OrderExportRequestedV1
from shop.application.outbox_messages import outbox_message
from shop.domain.errors.orders import UnsupportedExportFormatError
from shop.domain.events.orders import OrderExportRequestedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.request_order_export import RequestOrderExportDbGateway
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class RequestOrderExportResponse:
    """Public acknowledgement of a queued export."""

    job_id: str
    customer_id: int


@dataclass(frozen=True)
class RequestOrderExportRequest(Request[RequestOrderExportResponse]):
    """Describe an export to be executed outside the caller's lifecycle."""

    customer_id: int
    format: str = "csv"


class RequestOrderExportHandler(RequestHandler[RequestOrderExportRequest]):
    """Move export execution behind a queue-owned lifecycle."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: RequestOrderExportDbGateway,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._journal = journal

    async def __call__(self, request: RequestOrderExportRequest) -> RequestOrderExportResponse:
        if request.format not in {"csv", "jsonl"}:
            raise UnsupportedExportFormatError(request.format, ("csv", "jsonl"))
        event = OrderExportRequestedEvent(request.customer_id, request.format)
        message = outbox_message(OrderExportRequestedV1(request.customer_id, request.format))
        async with self._unit:
            await self._journal.append(event)
            await self._database.insert_outbox_message(message)
        job_id = message.message_id
        return RequestOrderExportResponse(job_id, request.customer_id)
