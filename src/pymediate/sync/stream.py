"""Synchronous streaming request handler for the mediator pattern."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from .._internal.stream import StreamHandlerBaseMixin
from ..stream import StreamRequest


class StreamRequestHandler[StreamReqT: StreamRequest[Any]](StreamHandlerBaseMixin[StreamReqT], ABC):
    """Abstract base class for synchronous streaming request handlers.

    The sync mirror of ``pymediate.StreamRequestHandler`` processes a
    ``StreamRequest`` by yielding chunks, consumed lazily through the synchronous
    ``Mediator.stream()``. Its type parameter names the stream request; that
    request's ``StreamRequest[ChunkT]`` declaration supplies the chunk type.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is a generator (uses `yield`)
    - The __call__ parameter annotates the exact declared request type
      (not a base class or union)
    - The __call__ return type is `Iterator[ChunkT]`, matching the request's chunk type

    Validation runs when Python executes the handler's class body, usually
    during import and before the handler is instantiated.

    Type Parameters:
        StreamReqT: The type of stream request this handler processes. Must inherit
            from StreamRequest; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Streaming an order export:
            ```python
            from collections.abc import Iterator
            from dataclasses import dataclass

            from pymediate.sync import StreamRequest, StreamRequestHandler

            @dataclass(frozen=True)
            class ExportOrders(StreamRequest[bytes]):
                customer_id: int

            class ExportOrdersHandler(StreamRequestHandler[ExportOrders]):
                def __call__(self, request: ExportOrders) -> Iterator[bytes]:
                    yield b"order_id,total_pence"
                    yield b"42,2500"
            ```

    Note:
        For asynchronous stream handlers, use `pymediate.StreamRequestHandler`
        instead. The `__call__` must be a generator (contain `yield`); a plain `def`
        that returns an iterator is rejected at class definition. Pipeline behaviors do
        not wrap `stream()`.

    Raises:
        InvalidStreamRequestTypeError: If the request type does not declare a chunk type.
        InvalidHandlerSignatureError: If __call__ isn't a correctly typed generator.
        HandlerAlreadyRegisteredError: If the request type already has a handler class.

    """

    _is_async = False  # Mark this as a synchronous stream handler

    @abstractmethod
    def __call__(self, request: StreamReqT) -> Iterator[Any]:
        """Handle the request and yield a stream of chunks.

        This is an abstract method that must be implemented by all sync
        StreamRequestHandler subclasses as a generator, with the signature
        `def __call__(self, request: RequestType) -> Iterator[ChunkType]: ...`
        and at least one `yield`.

        Args:
            request: The stream request to handle.

        Yields:
            Chunks of the type declared by the request's `StreamRequest[ChunkType]`.

        Note:
            The annotation must be the exact request class - a base class or union
            passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The method must be a
            generator; for async stream handlers, use
            `pymediate.StreamRequestHandler`.
        """
        ...
