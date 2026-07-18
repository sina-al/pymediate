"""FastAPI application factory for any named deployment container."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dependency_injector import containers
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from shop.bindings.loading import create_application_container, load_wiring
from shop.bindings.wiring import Wiring
from shop.openapi import api
from shop.openapi.errors import register_domain_error_handlers


def create_app(container: containers.Container | None = None) -> FastAPI:
    """Create the HTTP adapter and wire route dependencies to its container."""
    wiring: Wiring | None = load_wiring() if container is None else None
    application_container = (
        create_application_container(wiring) if wiring is not None else container
    )
    assert application_container is not None
    application_container.wire(modules=list(api.WIRING_MODULES))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if wiring is None:
            yield
        else:
            async with wiring.activate("application"):
                yield

    app = FastAPI(
        title="PyMediate Hexagonal Shop",
        version="1.0.0",
        description=(
            "Customer, order, invoice, statement, and audit operations through typed "
            "mediator requests."
        ),
        lifespan=lifespan,
    )
    app.state.container = application_container
    app.include_router(api.router)
    register_domain_error_handlers(app)
    FastAPIInstrumentor.instrument_app(app)

    return app
