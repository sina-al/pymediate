"""Verify integration contracts and trace propagation remain separate."""

from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from shop.application.integration_contracts import OrderConfirmationRequestedV1
from shop.application.outbox_messages import outbox_message
from shop.ports.integration import serialize_message


def test_outbox_message_captures_trace_context_outside_the_business_envelope() -> None:
    # Arrange
    span_context = SpanContext(
        trace_id=0x0AF7651916CD43DD8448EB211C80319C,
        span_id=0xB7AD6B7169203331,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    token = context.attach(trace.set_span_in_context(NonRecordingSpan(span_context)))

    # Act
    try:
        outbox = outbox_message(OrderConfirmationRequestedV1(42, 7))
    finally:
        context.detach(token)

    # Assert
    assert outbox.trace_context == {
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    }
    serialized = serialize_message(outbox.message)
    assert "traceparent" not in serialized
    assert '"payload":{"customer_id":7,"order_id":42}' in serialized
