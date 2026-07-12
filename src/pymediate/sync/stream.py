"""Synchronous streaming request handler for the mediator pattern."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from .._internal.stream import StreamHandlerBaseMixin
from ..stream import StreamRequest


class StreamRequestHandler[StreamReqT: StreamRequest[Any]](StreamHandlerBaseMixin[StreamReqT], ABC):
    """Abstract base class for synchronous streaming request handlers.

    The sync mirror of `pymediate.StreamRequestHandler`: a stream handler processes a
    `StreamRequest` by **yielding** a stream of chunks, consumed lazily via the sync
    `Mediator.stream()`. It only needs to specify the request type - the chunk type is
    inferred from the request's `StreamRequest[ChunkT]` declaration.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is a generator (uses `yield`)
    - The __call__ parameter annotates the exact declared request type
      (not a base class or union)
    - The __call__ return type is `Iterator[ChunkT]`, matching the request's chunk type

    This validation happens at class definition time (import time), catching errors
    early rather than at runtime.

    Type Parameters:
        StreamReqT: The type of stream request this handler processes. Must inherit
            from StreamRequest; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Streaming tokens for a completion request:
            ```python
            from collections.abc import Iterator
            from dataclasses import dataclass
            from pymediate.sync import StreamRequest, StreamRequestHandler

            @dataclass
            class StreamCompletion(StreamRequest[str]):
                prompt: str

            class CompletionHandler(StreamRequestHandler[StreamCompletion]):
                def __call__(self, request: StreamCompletion) -> Iterator[str]:
                    yield from request.prompt.split()
            ```

        Stream handler with dependencies:
            ```python
            class ExportRowsHandler(StreamRequestHandler[ExportRows]):
                def __init__(self, database: Database):
                    self.database = database

                def __call__(self, request: ExportRows) -> Iterator[Row]:
                    for row in self.database.iter_rows(request.table):
                        yield row
            ```

    Note:
        For asynchronous stream handlers, use `pymediate.StreamRequestHandler`
        instead. The `__call__` must be a generator (contain `yield`); a plain `def`
        that returns an iterator is rejected at class definition. Pipeline behaviors do
        not wrap `stream()`.

    Raises:
        InvalidStreamRequestTypeError: If the request type doesn't inherit from StreamRequest.
        InvalidHandlerSignatureError: If __call__ isn't a correctly typed generator.

    See Also:
        - StreamRequest: Base streaming request class.
        - Mediator.stream: Routes stream requests to stream handlers (sync version).
        - pymediate.StreamRequestHandler: Async stream handler variant.
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
