"""Export orders to replaceable storage, then announce the completed export."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.errors.orders import UnsupportedExportFormatError
from shop.ports.orders.export_orders import (
    ExportOrdersDbGateway,
    ExportOrdersMailer,
    ExportOrdersStorage,
)


@dataclass(frozen=True)
class ExportOrdersResponse:
    """Public location and size of a completed export."""

    url: str
    rows: int


@dataclass(frozen=True)
class ExportOrdersRequest(Request[ExportOrdersResponse]):
    """Request a customer's order history as a downloadable CSV."""

    customer_id: int
    format: str = "csv"
    idempotency_key: str | None = None


class ExportOrdersHandler(RequestHandler[ExportOrdersRequest]):
    """Stream orders into replaceable file storage."""

    def __init__(
        self,
        database: ExportOrdersDbGateway,
        storage: ExportOrdersStorage,
        mailer: ExportOrdersMailer,
    ) -> None:
        self._database = database
        self._storage = storage
        self._mailer = mailer

    async def __call__(self, request: ExportOrdersRequest) -> ExportOrdersResponse:
        if request.format not in {"csv", "jsonl"}:
            raise UnsupportedExportFormatError(request.format, ("csv", "jsonl"))
        count = 0

        async def rendered_rows() -> AsyncIterator[str]:
            nonlocal count
            if request.format == "csv":
                yield "order_id,total_pence,status\n"
            async for order in self._database.stream_orders(request.customer_id):
                count += 1
                if request.format == "csv":
                    yield f"{order.order_id},{order.total_pence},{order.status}\n"
                else:
                    yield (
                        f'{{"order_id":{order.order_id},"total_pence":{order.total_pence},'
                        f'"status":"{order.status}"}}\n'
                    )

        url = await self._storage.write(
            request.customer_id,
            request.format,
            rendered_rows(),
            idempotency_key=request.idempotency_key,
        )
        await self._mailer.send_export_ready(
            f"customer-{request.customer_id}@example.com",
            url,
            idempotency_key=request.idempotency_key,
        )
        return ExportOrdersResponse(url=url, rows=count)
