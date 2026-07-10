"""The doorways: every way a request can enter the application.

Web route, CLI command, queued job — each translates its own input format into a
request object and calls ``mediator.send()``. None of them know which persistence
adapter is wired in; they receive a finished ``Mediator`` from a composition root
in `apps/` and never look behind it.
"""
