"""A late-bound handle to the mediator — the clean way past the construction cycle.

A composing handler needs to `send()` sub-requests, so it needs the mediator. But the
mediator can't be built until every handler — the composing one included — is registered
in the provider. That's a three-way cycle: provider → orchestrator → mediator → provider.

Injecting a `Dispatcher` instead of the mediator itself breaks it. The orchestrator
receives this handle at construction (ordinary constructor injection); `build_mediator`
fills in the real mediator as its final wiring step, once the mediator exists. The
orchestrator never holds another handler — only this send-capable handle.

This is the synchronous mirror of `examples/050-handler-composition/dispatch.py` — same
handle, plain `def send` instead of `async def`.
"""

from pymediate.sync import Mediator, Request


class Dispatcher:
    """A send-capable handle whose mediator is bound after construction.

    Exposes just `send`, with the same typed signature as `Mediator.send`, so a handler
    can depend on "something I can send through" without depending on how it was wired.
    """

    def __init__(self) -> None:
        self._mediator: Mediator | None = None

    def bind(self, mediator: Mediator) -> None:
        """Attach the mediator. Called once, by `build_mediator`, after the mediator exists."""
        self._mediator = mediator

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request through the bound mediator and return its typed response.

        Raises:
            RuntimeError: If called before `build_mediator` has bound the mediator.
        """
        if self._mediator is None:
            raise RuntimeError("Dispatcher.send called before the mediator was bound")
        return self._mediator.send(request)
