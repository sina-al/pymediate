"""Tests for async Handler and Mediator classes."""

import asyncio

import pytest

from pymediate import (
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    Request,
    ResponseTypeMismatchError,
    Services,
)
from pymediate._internal.registry import get_handler_class, has_handler
from pymediate.aio import Handler, Mediator


def test_async_handler_extracts_request_type() -> None:
    """Test that async Handler extracts request type from generic."""

    class TestResponse:
        def __init__(self, value: int):
            self.value = value

    class TestRequest(Request[TestResponse]):
        def __init__(self, data: str):
            self.data = data

    class TestHandler(Handler[TestRequest]):
        async def __call__(self, request: TestRequest) -> TestResponse:
            return TestResponse(42)

    assert TestHandler._request_type == TestRequest
    assert TestHandler._response_type == TestResponse


def test_async_handler_registration() -> None:
    """Test that async Handler is registered in handler registry."""

    class Response:
        pass

    class Req(Request[Response]):
        pass

    class ReqHandler(Handler[Req]):
        async def __call__(self, request: Req) -> Response:
            return Response()

    assert has_handler(Req)
    assert get_handler_class(Req) == ReqHandler


def test_async_handler_validates_correct_return_type() -> None:
    """Test that async Handler with correct return type is accepted."""

    class GoodResponse:
        def __init__(self, msg: str):
            self.msg = msg

    class GoodRequest(Request[GoodResponse]):
        pass

    # This should not raise
    class GoodHandler(Handler[GoodRequest]):
        async def __call__(self, request: GoodRequest) -> GoodResponse:
            return GoodResponse("ok")

    assert GoodHandler._response_type == GoodResponse


def test_async_handler_rejects_wrong_return_type() -> None:
    """Test that async Handler with wrong return type is rejected."""

    class CorrectResponse:
        pass

    class WrongResponse:
        pass

    class ReqWithCorrectResponse(Request[CorrectResponse]):
        pass

    # This should raise ResponseTypeMismatchError
    with pytest.raises(ResponseTypeMismatchError):

        class BadHandler(Handler[ReqWithCorrectResponse]):
            async def __call__(self, request: ReqWithCorrectResponse) -> WrongResponse:
                return WrongResponse()


def test_async_handler_rejects_sync_call() -> None:
    """Test that async Handler rejects sync __call__ method."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    # This should raise InvalidHandlerSignatureError because __call__ must be async
    with pytest.raises(InvalidHandlerSignatureError, match="__call__ must be async"):

        class BadHandler(Handler[Req]):
            def __call__(self, request: Req) -> Resp:  # Missing async!
                return Resp()


def test_async_event_handler_rejects_sync_call() -> None:
    """Test that the async EventHandler rejects a sync __call__."""
    from pymediate import Event
    from pymediate.aio import EventHandler

    class Ping(Event):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="__call__ must be async"):

        class Bad(EventHandler[Ping]):
            def __call__(self, event: Ping) -> None:
                pass


@pytest.mark.asyncio
async def test_async_publish_runs_handlers_concurrently_and_aggregates() -> None:
    """Test concurrent fan-out: all handlers run, failures aggregate, order via gather."""
    import asyncio
    from dataclasses import dataclass

    from pymediate import Event
    from pymediate.aio import EventHandler
    from pymediate.aio import Mediator as AioMediator

    @dataclass
    class Ping(Event):
        pass

    completed: list[str] = []

    class SlowSubscriber(EventHandler[Ping]):
        async def __call__(self, event: Ping) -> None:
            await asyncio.sleep(0.05)
            completed.append("slow")

    class FastSubscriber(EventHandler[Ping]):
        async def __call__(self, event: Ping) -> None:
            completed.append("fast")

    class FailingSubscriber(EventHandler[Ping]):
        async def __call__(self, event: Ping) -> None:
            raise ValueError("async boom")

    services = Services()
    services.add(SlowSubscriber()).add(FastSubscriber()).add(FailingSubscriber())
    mediator = AioMediator(services.provider())

    with pytest.raises(ExceptionGroup) as excinfo:
        await mediator.publish(Ping())

    # Every handler ran; the fast one finished before the slow one despite
    # registering after it - proof the fan-out is concurrent, not sequential.
    assert completed == ["fast", "slow"]
    assert "1 of 3 event handlers raised while publishing Ping" in str(excinfo.value)
    assert {type(exc) for exc in excinfo.value.exceptions} == {ValueError}


@pytest.mark.asyncio
async def test_async_publish_with_zero_handlers_is_a_no_op() -> None:
    """Test that async publish with no subscribers succeeds silently."""
    from pymediate import Event
    from pymediate.aio import Mediator as AioMediator

    class NobodyListens(Event):
        pass

    mediator = AioMediator(Services().provider())
    await mediator.publish(NobodyListens())  # Must not raise.


def test_async_handler_rejects_base_class_parameter_annotation() -> None:
    """Test that the async mirror also rejects a base-class parameter annotation."""

    class Resp:
        pass

    class BaseReq(Request[Resp]):
        pass

    class DerivedReq(BaseReq):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="a base class of DerivedReq"):

        class BadHandler(Handler[DerivedReq]):
            async def __call__(self, request: BaseReq) -> Resp:
                return Resp()


def test_sync_handler_rejects_async_call() -> None:
    """Test that sync Handler rejects async __call__ method."""
    from pymediate import Handler as SyncHandler

    class Resp:
        pass

    class Req2(Request[Resp]):
        pass

    # This should raise InvalidHandlerSignatureError because __call__ must be sync
    with pytest.raises(InvalidHandlerSignatureError, match="__call__ must be sync"):

        class BadSyncHandler(SyncHandler[Req2]):
            async def __call__(self, request: Req2) -> Resp:  # Should not be async!
                return Resp()


@pytest.mark.asyncio
async def test_async_handler_call() -> None:
    """Test that async handler can be called."""

    class NumResponse:
        def __init__(self, result: int):
            self.result = result

    class NumRequest(Request[NumResponse]):
        def __init__(self, value: int):
            self.value = value

    class DoubleHandler(Handler[NumRequest]):
        async def __call__(self, request: NumRequest) -> NumResponse:
            # Simulate async operation
            await asyncio.sleep(0.001)
            return NumResponse(request.value * 2)

    handler = DoubleHandler()
    request = NumRequest(21)
    response = await handler(request)

    assert isinstance(response, NumResponse)
    assert response.result == 42


@pytest.mark.asyncio
async def test_async_mediator_creation() -> None:
    """Test that async Mediator can be created with a resolver."""
    services = Services()
    provider = services.provider()
    mediator = Mediator(provider)
    assert mediator is not None


@pytest.mark.asyncio
async def test_async_mediator_send_request() -> None:
    """Test sending a request through async mediator."""

    class GreetingResponse:
        def __init__(self, message: str):
            self.message = message

    class GreetingRequest(Request[GreetingResponse]):
        def __init__(self, name: str):
            self.name = name

    class GreetingHandler(Handler[GreetingRequest]):
        async def __call__(self, request: GreetingRequest) -> GreetingResponse:
            await asyncio.sleep(0.001)
            return GreetingResponse(f"Hello, {request.name}!")

    services = Services()
    services.add(GreetingHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    request = GreetingRequest("Alice")
    response = await mediator.send(request)

    assert isinstance(response, GreetingResponse)
    assert response.message == "Hello, Alice!"


@pytest.mark.asyncio
async def test_async_mediator_send_unregistered_request() -> None:
    """Test that sending unregistered request raises HandlerNotFoundError."""

    class UnhandledResp:
        pass

    class UnhandledReq(Request[UnhandledResp]):
        def __init__(self, data: str):
            self.data = data

    services = Services()
    provider = services.provider()
    mediator = Mediator(provider)

    with pytest.raises(HandlerNotFoundError):
        await mediator.send(UnhandledReq("test"))


@pytest.mark.asyncio
async def test_async_mediator_with_multiple_handlers() -> None:
    """Test async mediator with multiple request/handler pairs."""

    class AddResponse:
        def __init__(self, result: int):
            self.result = result

    class MultiplyResponse:
        def __init__(self, result: int):
            self.result = result

    class AddRequest(Request[AddResponse]):
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    class MultiplyRequest(Request[MultiplyResponse]):
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    class AddHandler(Handler[AddRequest]):
        async def __call__(self, request: AddRequest) -> AddResponse:
            await asyncio.sleep(0.001)
            return AddResponse(request.a + request.b)

    class MultiplyHandler(Handler[MultiplyRequest]):
        async def __call__(self, request: MultiplyRequest) -> MultiplyResponse:
            await asyncio.sleep(0.001)
            return MultiplyResponse(request.a * request.b)

    services = Services()
    services.add(AddHandler())
    services.add(MultiplyHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    add_result = await mediator.send(AddRequest(5, 3))
    mult_result = await mediator.send(MultiplyRequest(5, 3))

    assert add_result.result == 8
    assert mult_result.result == 15


@pytest.mark.asyncio
async def test_async_mediator_with_stateful_handler() -> None:
    """Test async mediator with a handler that maintains state."""

    class CountResponse:
        def __init__(self, count: int):
            self.count = count

    class CountRequest(Request[CountResponse]):
        pass

    class CounterHandler(Handler[CountRequest]):
        def __init__(self) -> None:
            self.count = 0

        async def __call__(self, request: CountRequest) -> CountResponse:
            await asyncio.sleep(0.001)
            self.count += 1
            return CountResponse(self.count)

    services = Services()
    handler = CounterHandler()
    services.add(handler)
    provider = services.provider()
    mediator = Mediator(provider)

    resp1 = await mediator.send(CountRequest())
    resp2 = await mediator.send(CountRequest())
    resp3 = await mediator.send(CountRequest())

    assert resp1.count == 1
    assert resp2.count == 2
    assert resp3.count == 3


@pytest.mark.asyncio
async def test_async_handler_with_actual_async_operations() -> None:
    """Test async handler that performs actual async operations."""

    class FetchResponse:
        def __init__(self, data: str):
            self.data = data

    class FetchRequest(Request[FetchResponse]):
        def __init__(self, url: str):
            self.url = url

    async def mock_fetch(url: str) -> str:
        """Mock async fetch operation."""
        await asyncio.sleep(0.01)
        return f"data from {url}"

    class FetchHandler(Handler[FetchRequest]):
        async def __call__(self, request: FetchRequest) -> FetchResponse:
            data = await mock_fetch(request.url)
            return FetchResponse(data)

    services = Services()
    services.add(FetchHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = await mediator.send(FetchRequest("https://example.com"))
    assert response.data == "data from https://example.com"


@pytest.mark.asyncio
async def test_async_mediator_error_propagation() -> None:
    """Test that errors in async handlers are propagated through mediator."""

    class ErrorResponse:
        pass

    class ErrorRequest(Request[ErrorResponse]):
        pass

    class ErrorHandler(Handler[ErrorRequest]):
        async def __call__(self, request: ErrorRequest) -> ErrorResponse:
            await asyncio.sleep(0.001)
            raise RuntimeError("Async handler error")

    services = Services()
    services.add(ErrorHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    with pytest.raises(RuntimeError, match="Async handler error"):
        await mediator.send(ErrorRequest())


@pytest.mark.asyncio
async def test_async_mediator_concurrent_requests() -> None:
    """Test that async mediator can handle concurrent requests."""

    class SlowResponse:
        def __init__(self, value: int):
            self.value = value

    class SlowRequest(Request[SlowResponse]):
        def __init__(self, value: int, delay: float):
            self.value = value
            self.delay = delay

    class SlowHandler(Handler[SlowRequest]):
        async def __call__(self, request: SlowRequest) -> SlowResponse:
            await asyncio.sleep(request.delay)
            return SlowResponse(request.value * 2)

    services = Services()
    services.add(SlowHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    # Send three concurrent requests
    results = await asyncio.gather(
        mediator.send(SlowRequest(1, 0.01)),
        mediator.send(SlowRequest(2, 0.01)),
        mediator.send(SlowRequest(3, 0.01)),
    )

    assert len(results) == 3
    assert results[0].value == 2
    assert results[1].value == 4
    assert results[2].value == 6


@pytest.mark.asyncio
async def test_async_handler_with_complex_async_flow() -> None:
    """Test async handler with complex async control flow."""

    class ProcessResponse:
        def __init__(self, results: list[int]):
            self.results = results

    class ProcessRequest(Request[ProcessResponse]):
        def __init__(self, items: list[int]):
            self.items = items

    async def process_item(item: int) -> int:
        """Simulate async processing of an item."""
        await asyncio.sleep(0.001)
        return item * item

    class ProcessHandler(Handler[ProcessRequest]):
        async def __call__(self, request: ProcessRequest) -> ProcessResponse:
            # Process all items concurrently
            results = await asyncio.gather(*[process_item(item) for item in request.items])
            return ProcessResponse(list(results))

    services = Services()
    services.add(ProcessHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = await mediator.send(ProcessRequest([1, 2, 3, 4, 5]))
    assert response.results == [1, 4, 9, 16, 25]
