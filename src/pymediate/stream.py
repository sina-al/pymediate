"""Streaming request base class and asynchronous stream handler for the mediator pattern."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ._internal import registry
from ._internal.stream import StreamHandlerBaseMixin


class StreamRequest[ChunkT]:
    """Base class for requests answered by a stream of typed chunks.

    Where a `Request[ResponseT]` is answered by exactly one response and an `Event`
    is published to zero or more handlers, a `StreamRequest[ChunkT]` is answered by
    exactly one handler that **yields** a stream of `ChunkT` values, consumed lazily
    via `Mediator.stream()`. Inherit from `StreamRequest[ChunkT]` to declare the
    element type of that stream - LLM tokens, paginated rows, export records.

    The chunk type is extracted and registered automatically when the class is
    defined, so `stream()` infers the element type at the call site with no casts.
    `StreamRequest` is deliberately separate from `Request`: `stream()` accepts only
    `StreamRequest` and `send()` only `Request`, so mixing them up is a type error.

    This class works seamlessly with dataclasses, regular classes, and any Python
    class structure.

    Type Parameters:
        ChunkT: The type of each item the handler yields for this request.

    Examples:
        Declaring a streaming request:
            ```python
            from dataclasses import dataclass
            from pymediate import StreamRequest

            @dataclass
            class StreamCompletion(StreamRequest[str]):
                prompt: str
            ```

    Note:
        The chunk type is registered at import time, not at runtime, so there is no
        performance penalty for using this pattern.

    See Also:
        - StreamRequestHandler: Async handler that yields the stream (this module).
        - Mediator.stream: Routes a stream request to its handler.
        - Request: The one-handler, single-response counterpart.
        - pymediate.sync.StreamRequestHandler: Sync stream handler variant.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the chunk type when a StreamRequest subclass is created.

        This hook is automatically called when a new StreamRequest subclass is defined.
        It extracts the chunk type from the generic type parameter and stores it in the
        global registry for handler validation and element-type inference.

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

    A stream handler processes a `StreamRequest` by **yielding** a stream of chunks
    asynchronously. It only needs to specify the request type - the chunk type is
    inferred from the request's `StreamRequest[ChunkT]` declaration.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is an async generator (uses `yield`)
    - The __call__ parameter annotates the exact declared request type
      (not a base class or union)
    - The __call__ return type is `AsyncIterator[ChunkT]`, matching the request's chunk type

    This validation happens at class definition time (import time), catching errors
    early rather than at runtime.

    Type Parameters:
        StreamReqT: The type of stream request this handler processes. Must inherit
            from StreamRequest; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Streaming tokens for a completion request:
            ```python
            from collections.abc import AsyncIterator
            from dataclasses import dataclass
            from pymediate import StreamRequest, StreamRequestHandler

            @dataclass
            class StreamCompletion(StreamRequest[str]):
                prompt: str

            class CompletionHandler(StreamRequestHandler[StreamCompletion]):
                async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
                    for token in request.prompt.split():
                        yield token
            ```

        Delegating to an existing async stream:
            ```python
            class CompletionHandler(StreamRequestHandler[StreamCompletion]):
                def __init__(self, client: LLMClient):
                    self.client = client

                async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
                    async for token in self.client.stream(request.prompt):
                        yield token
            ```

    Note:
        For synchronous stream handlers, use `pymediate.sync.StreamRequestHandler`
        instead. The `__call__` must be an async generator (contain `yield`); a plain
        `async def` that returns an iterator is rejected at class definition. Pipeline
        behaviors do not wrap `stream()`.

    Raises:
        InvalidStreamRequestTypeError: If the request type doesn't inherit from StreamRequest.
        InvalidHandlerSignatureError: If __call__ isn't a correctly typed async generator.

    See Also:
        - StreamRequest: Base streaming request class.
        - Mediator.stream: Routes stream requests to async stream handlers.
        - pymediate.sync.StreamRequestHandler: Sync stream handler variant.
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
