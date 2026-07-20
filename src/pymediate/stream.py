"""Streaming request base class and asynchronous stream handler for the mediator pattern."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ._internal import registry
from ._internal.stream import StreamHandlerBaseMixin


class StreamRequest[ChunkT]:
    """Base class for requests answered by a stream of typed chunks.

    Where a `Request[ResponseT]` is answered by exactly one response and an `Notification`
    is published to zero or more handlers, a `StreamRequest[ChunkT]` is answered by
    exactly one handler that yields a stream of ``ChunkT`` values, consumed lazily
    through ``Mediator.stream()``. Inherit from ``StreamRequest[ChunkT]`` to
    declare the element type of that stream.

    The generic declaration lets a static type checker infer the element type
    returned by ``stream()``. Separately, PyMediate records the chunk type when
    Python defines the request class so it can validate the stream handler's
    annotations. ``StreamRequest`` is separate from ``Request``: ``stream()``
    accepts stream requests, while ``send()`` accepts single-response requests.

    Stream request subclasses can be dataclasses or regular classes.

    Type Parameters:
        ChunkT: The type of each item the handler yields for this request.

    Examples:
        Declaring an order export:
            ```python
            from dataclasses import dataclass

            from pymediate import StreamRequest

            @dataclass(frozen=True)
            class ExportOrders(StreamRequest[bytes]):
                customer_id: int
            ```

    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the chunk type when a StreamRequest subclass is created.

        This hook is automatically called when a new StreamRequest subclass is defined.
        It extracts the chunk type from the generic type parameter and stores it in the
        global registry for handler annotation validation.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Note:
            This method is called automatically by Python when a subclass is created.
            You should not call this method directly.
        """
        super().__init_subclass__(**kwargs)

        if orig_bases := getattr(cls, "__orig_bases__", None):
            for base in orig_bases:
                if getattr(base, "__origin__", None) is StreamRequest:
                    if args := getattr(base, "__args__", None):
                        chunk_type = args[0]
                        registry.register_request_response_type(cls, chunk_type)
                        break


class StreamRequestHandler[StreamReqT: StreamRequest[Any]](StreamHandlerBaseMixin[StreamReqT], ABC):
    """Abstract base class for asynchronous streaming request handlers.

    A stream handler processes a ``StreamRequest`` by yielding chunks
    asynchronously. Its type parameter names the stream request; that request's
    ``StreamRequest[ChunkT]`` declaration supplies the chunk type.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is an async generator (uses `yield`)
    - The __call__ parameter annotates the exact declared request type
      (not a base class or union)
    - The __call__ return type is `AsyncIterator[ChunkT]`, matching the request's chunk type

    Validation runs when Python executes the handler's class body, usually
    during import and before the handler is instantiated.

    Type Parameters:
        StreamReqT: The type of stream request this handler processes. Must inherit
            from StreamRequest; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Streaming an order export:
            ```python
            from collections.abc import AsyncIterator
            from dataclasses import dataclass

            from pymediate import StreamRequest, StreamRequestHandler

            @dataclass(frozen=True)
            class ExportOrders(StreamRequest[bytes]):
                customer_id: int

            class ExportOrdersHandler(StreamRequestHandler[ExportOrders]):
                async def __call__(self, request: ExportOrders) -> AsyncIterator[bytes]:
                    yield b"order_id,total_pence"
                    yield b"42,2500"
            ```

    Note:
        For synchronous stream handlers, use `pymediate.sync.StreamRequestHandler`
        instead. The `__call__` must be an async generator (contain `yield`); a plain
        `async def` that returns an iterator is rejected at class definition. Pipeline
        behaviors do not wrap `stream()`.

    Raises:
        InvalidStreamRequestTypeError: If the request type does not declare a chunk type.
        InvalidHandlerSignatureError: If __call__ isn't a correctly typed async generator.
        HandlerAlreadyRegisteredError: If the request type already has a handler class.

    """

    _is_async = True  # Mark this as an asynchronous stream handler

    @abstractmethod
    def __call__(self, request: StreamReqT) -> AsyncIterator[Any]:
        """Handle the request and yield a stream of chunks asynchronously.

        This is an abstract method that must be implemented by all async
        StreamRequestHandler subclasses as an async generator, with the signature
        `async def __call__(self, request: RequestType) -> AsyncIterator[ChunkType]: ...`
        and at least one `yield`.

        Args:
            request: The stream request to handle.

        Yields:
            Chunks of the type declared by the request's `StreamRequest[ChunkType]`.

        Note:
            The annotation must be the exact request class - a base class or union
            passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The method must be an
            async generator; for sync stream handlers, use
            `pymediate.sync.StreamRequestHandler`.
        """
        ...
