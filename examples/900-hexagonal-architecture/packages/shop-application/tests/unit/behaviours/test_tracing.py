"""Verify mediator tracing uses OpenTelemetry without exposing request payloads."""

from dataclasses import dataclass

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pymediate import Request

from shop.application.behaviours.tracing import TracingBehavior


@dataclass(frozen=True)
class ExampleRequest(Request[str]):
    secret: str


def telemetry() -> tuple[TracingBehavior, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return TracingBehavior(provider.get_tracer("test")), exporter


async def test_tracing_records_request_shape_and_response_without_payloads() -> None:
    # Arrange
    behavior, exporter = telemetry()

    # Act
    response = await behavior(ExampleRequest("do-not-record"), lambda: _result("done"))

    # Assert
    span = exporter.get_finished_spans()[0]
    assert response == "done"
    assert span.name == "ExampleRequest"
    assert span.attributes == {
        "shop.request.type": "ExampleRequest",
        "shop.request.module": __name__,
        "shop.response.type": "str",
    }
    assert "do-not-record" not in str(span.attributes)


async def test_tracing_records_and_reraises_failures() -> None:
    # Arrange
    behavior, exporter = telemetry()

    # Act
    with pytest.raises(RuntimeError, match="failed"):
        await behavior(ExampleRequest("secret"), _failure)

    # Assert
    span = exporter.get_finished_spans()[0]
    assert span.attributes is not None
    assert span.attributes["error.type"] == "RuntimeError"
    assert span.events[0].name == "exception"


async def _result(value: str) -> str:
    return value


async def _failure() -> str:
    raise RuntimeError("failed")
