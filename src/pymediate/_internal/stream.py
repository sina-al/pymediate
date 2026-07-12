"""Shared base logic for both sync and async streaming request handlers.

This module provides StreamHandlerBaseMixin, which contains the type extraction,
validation, and registration logic common between sync and async stream handlers.
It reuses the exact-annotation validator pieces from handler.py; the stream-specific
differences are the generator __call__ form and the Iterator[ChunkT] /
AsyncIterator[ChunkT] return contract.
"""

import collections.abc
import inspect
from typing import Any, get_args, get_origin

from .. import errors
from . import registry
from .handler import (
    _qualified_name,
    _require_call_method,
    _resolve_call_annotations,
    _validate_request_annotation,
)


def _validate_stream_call_signature(
    cls: type,
    expected_request_type: type,
    expected_chunk_type: object,
    *,
    is_async: bool,
) -> None:
    """Validate that a stream handler's __call__ is a correctly typed generator.

    Stream handlers must be generators (they ``yield`` chunks) and annotate their
    return as ``Iterator[ChunkT]`` (sync) or ``AsyncIterator[ChunkT]`` (async), where
    ``ChunkT`` is the chunk type declared on the ``StreamRequest``. The request
    parameter is held to ADR 0004's exact-annotation contract, same as request and
    event handlers.

    Args:
        cls: The stream handler class to validate.
        expected_request_type: The exact StreamRequest class the parameter must annotate.
        expected_chunk_type: The chunk type declared on the StreamRequest.
        is_async: Whether to expect an async generator or a sync generator.

    Raises:
        InvalidHandlerSignatureError: If __call__ isn't a generator of the right form,
            the request annotation isn't exact, or the return annotation isn't the
            expected iterator type.
    """
    call_method = _require_call_method(cls)

    # A stream handler yields; require the generator form (an async-generator function
    # is NOT a coroutine function, so iscoroutinefunction can't be used here).
    if is_async and not inspect.isasyncgenfunction(call_method):
        raise errors.InvalidHandlerSignatureError(
            cls,
            "__call__ must be an async generator - use 'async def __call__' with at "
            "least one 'yield' (a plain 'async def' that returns an iterator is rejected)",
        )
    if not is_async and not inspect.isgeneratorfunction(call_method):
        raise errors.InvalidHandlerSignatureError(
            cls,
            "__call__ must be a generator - use 'def __call__' with at least one 'yield' "
            "(a plain 'def' that returns an iterator is rejected)",
        )

    request_annotation, return_annotation = _resolve_call_annotations(cls, call_method)
    _validate_request_annotation(
        cls,
        request_annotation,
        expected_request_type,
        kind="request",
        declaration_name="StreamRequestHandler",
    )

    expected_origin = collections.abc.AsyncIterator if is_async else collections.abc.Iterator
    iterator_name = "AsyncIterator" if is_async else "Iterator"
    # Compare by origin + args so both the collections.abc and typing spellings of
    # Iterator/AsyncIterator are accepted (their subscripted forms aren't == equal).
    if get_origin(return_annotation) is not expected_origin or get_args(return_annotation) != (
        expected_chunk_type,
    ):
        raise errors.InvalidHandlerSignatureError(
            cls,
            f"__call__ must be annotated to return {iterator_name}"
            f"[{_qualified_name(expected_chunk_type)}] - a stream handler yields the "
            f"request's chunk type, got {_qualified_name(return_annotation)}",
        )


class StreamHandlerBaseMixin[StreamReqT]:
    """Mixin providing shared logic for both sync and async stream handlers.

    This mixin extracts the stream request type from ``StreamRequestHandler[StreamReqT]``,
    looks up the chunk type declared on that request, validates the generator ``__call__``
    signature, and registers the handler in the one-handler-per-request registry.

    Type Parameters:
        StreamReqT: The StreamRequest type this handler processes.

    Attributes:
        _stream_request_type: Class-level attribute storing the stream request type.
        _chunk_type: Class-level attribute storing the inferred chunk type.
    """

    _stream_request_type: type | None = None
    _chunk_type: object | None = None
    _is_async: bool = False  # Set by subclass

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Extract the stream request type, validate __call__, and register the handler.

        This hook is automatically called when a new StreamRequestHandler subclass is
        defined. It extracts the stream request type from
        ``StreamRequestHandler[StreamReqType]``, looks up the chunk type, validates the
        generator ``__call__`` signature, and registers the handler.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Raises:
            InvalidStreamRequestTypeError: If the type parameter doesn't inherit from
                StreamRequest (or has no declared chunk type).
            InvalidHandlerSignatureError: If the generator __call__ signature is invalid.
        """
        super().__init_subclass__(**kwargs)

        cls._stream_request_type = None
        cls._chunk_type = None

        # Extract stream request type from StreamRequestHandler[StreamReqType]; find the
        # base whose origin is a StreamRequestHandler-like class (has this mixin in mro).
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            if origin and StreamHandlerBaseMixin in getattr(origin, "__mro__", []):
                args = get_args(base)
                if args:
                    cls._stream_request_type = args[0]
                    break

        if cls._stream_request_type is None:
            return

        # Imported lazily: pymediate.stream imports this module at import time.
        from ..stream import StreamRequest

        if not (
            isinstance(cls._stream_request_type, type)
            and issubclass(cls._stream_request_type, StreamRequest)
        ):
            # Skip the base classes themselves, whose type argument is a TypeVar.
            if cls.__name__ not in ("StreamRequestHandler", "StreamHandlerBaseMixin"):
                raise errors.InvalidStreamRequestTypeError(cls._stream_request_type)
            return

        # The chunk type is stored in the request registry by StreamRequest.__init_subclass__.
        # A StreamRequest subclass with no declared chunk type is unusable as a stream.
        if not registry.has_response_type(cls._stream_request_type):
            raise errors.InvalidStreamRequestTypeError(cls._stream_request_type)

        cls._chunk_type = registry.get_response_type(cls._stream_request_type)
        _validate_stream_call_signature(
            cls, cls._stream_request_type, cls._chunk_type, is_async=cls._is_async
        )
        registry.register_handler(cls._stream_request_type, cls)

    @classmethod
    def get_stream_request_type(cls) -> type | None:
        """Get the stream request type this handler processes.

        Returns:
            The StreamRequest type this handler is designed to process, or None if no
            stream request type was specified.
        """
        return cls._stream_request_type

    @classmethod
    def get_chunk_type(cls) -> object | None:
        """Get the chunk type this handler yields.

        The chunk type is automatically inferred from the request's
        ``StreamRequest[ChunkT]`` declaration.

        Returns:
            The chunk type this handler yields, or None if no chunk type was registered.
        """
        return cls._chunk_type
