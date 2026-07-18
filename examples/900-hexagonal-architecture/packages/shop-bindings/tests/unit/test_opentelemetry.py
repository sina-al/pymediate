"""Verify bindings configure the standard OpenTelemetry SDK."""

from typing import cast

import pytest
from opentelemetry import metrics, trace
from opentelemetry.metrics import MeterProvider as ApiMeterProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import TracerProvider as ApiTracerProvider

from shop.bindings.opentelemetry import configure_opentelemetry


async def test_configures_standard_sdk_providers_from_otel_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    installed: dict[str, ApiTracerProvider | ApiMeterProvider] = {}
    monkeypatch.setenv("OTEL_SERVICE_NAME", "shop-test")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setattr(
        trace,
        "set_tracer_provider",
        lambda provider: installed.__setitem__("tracer", provider),
    )
    monkeypatch.setattr(
        metrics,
        "set_meter_provider",
        lambda provider: installed.__setitem__("meter", provider),
    )

    # Act
    async with configure_opentelemetry():
        tracer_provider = cast("TracerProvider", installed["tracer"])
        meter_provider = cast("MeterProvider", installed["meter"])

    # Assert
    assert isinstance(tracer_provider, TracerProvider)
    assert isinstance(meter_provider, MeterProvider)
    assert tracer_provider.resource.attributes["service.name"] == "shop-test"


async def test_standard_sdk_disabled_flag_disables_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    installed: dict[str, ApiTracerProvider] = {}
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setattr(
        trace,
        "set_tracer_provider",
        lambda provider: installed.__setitem__("tracer", provider),
    )
    monkeypatch.setattr(metrics, "set_meter_provider", lambda provider: None)

    # Act
    async with configure_opentelemetry():
        span = installed["tracer"].get_tracer("test").start_span("disabled")

    # Assert
    assert not span.is_recording()
