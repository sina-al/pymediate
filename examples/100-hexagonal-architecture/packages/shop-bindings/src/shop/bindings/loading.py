"""Load application composition from a deployment provider manifest."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from shop.application.container import ApplicationContainer
from shop.bindings.settings import BootstrapSettings, settings_from_environment
from shop.bindings.wiring import Wiring, create_wiring


def load_wiring(path: str | Path | None = None) -> Wiring:
    """Resolve the provider graph selected by ``SHOP_WIRING`` or an explicit path."""
    settings = (
        BootstrapSettings.model_validate({"wiring": path})
        if path is not None
        else settings_from_environment(BootstrapSettings)
    )
    return create_wiring(settings.wiring)


def create_application_container(wiring: Wiring) -> ApplicationContainer:
    """Compose an application container from a resolved provider graph.

    Activate the application role before resolving resource-backed services from
    the returned container. :func:`application_context` owns both operations for
    executable code.
    """
    bindings = wiring.role(
        "application",
        set(ApplicationContainer.dependencies),
    ).providers
    container = ApplicationContainer(**bindings)
    container.check_dependencies()
    return container


@asynccontextmanager
async def application_context(
    path: str | Path | None = None,
) -> AsyncIterator[ApplicationContainer]:
    """Yield an application container while its selected resources are active."""
    wiring = load_wiring(path)
    async with wiring.activate("application"):
        yield create_application_container(wiring)


def load_container(path: str | Path | None = None) -> ApplicationContainer:
    """Build an application container without owning its resource lifecycle.

    Use :func:`application_context` for executable code. This helper exists for
    composition inspection and tests that do not resolve resource providers.
    """
    return create_application_container(load_wiring(path))
