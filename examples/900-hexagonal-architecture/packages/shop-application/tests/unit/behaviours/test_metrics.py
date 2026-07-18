"""Verify mediator metrics use bounded OpenTelemetry attributes."""

from dataclasses import dataclass

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    HistogramDataPoint,
    InMemoryMetricReader,
    NumberDataPoint,
)
from pymediate import Request

from shop.application.behaviours.metrics import MetricsBehavior


@dataclass(frozen=True)
class ExampleRequest(Request[str]):
    customer_id: int


def telemetry() -> tuple[MetricsBehavior, InMemoryMetricReader]:
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader]).get_meter("test")
    times = iter((1.0, 1.025))
    return MetricsBehavior(meter, lambda: next(times)), reader


@pytest.mark.parametrize("fails", [False, True])
async def test_metrics_record_bounded_outcome_and_duration(fails: bool) -> None:
    # Arrange
    behavior, reader = telemetry()

    # Act
    if fails:
        with pytest.raises(RuntimeError):
            await behavior(ExampleRequest(987654321), _failure)
    else:
        assert await behavior(ExampleRequest(987654321), lambda: _result("done")) == "done"

    # Assert
    data = reader.get_metrics_data()
    assert data is not None
    metrics = data.resource_metrics[0].scope_metrics[0].metrics
    points = {metric.name: metric.data.data_points[0] for metric in metrics}
    expected = {
        "request.type": "ExampleRequest",
        "request.outcome": "error" if fails else "success",
    }
    if fails:
        expected["error.type"] = "RuntimeError"
    count = points["shop.application.requests"]
    duration = points["shop.application.request.duration"]
    assert isinstance(count, NumberDataPoint)
    assert isinstance(duration, HistogramDataPoint)
    assert count.attributes is not None
    assert dict(count.attributes) == expected
    assert count.value == 1
    assert duration.sum == pytest.approx(25.0)
    assert "987654321" not in str(expected)


async def _result(value: str) -> str:
    return value


async def _failure() -> str:
    raise RuntimeError("failed")
