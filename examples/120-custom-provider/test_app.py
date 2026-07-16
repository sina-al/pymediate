"""Tests for the custom-provider example.

Two things are under test: the adapter's five Protocol methods in isolation, and the
promise that motivates the whole example — the same `mediator.send()` call site works
identically whether the mediator was built from `Services.provider()` or from
`TypeRegistryServiceProvider`.
"""

import pytest
from pymediate import Mediator, ServiceNotFoundError, Services

from app import (
    Add,
    AddHandler,
    Logger,
    MultiplyHandler,
    TypeRegistry,
    TypeRegistryServiceProvider,
    build_mediator,
    build_registry,
)

# ---- The adapter's five Protocol methods, in isolation ----


def test_get_returns_the_registered_instance() -> None:
    logger = Logger()
    provider = TypeRegistryServiceProvider(build_registry(logger))

    assert provider.get(Logger) is logger


def test_get_raises_for_an_unregistered_type() -> None:
    provider = TypeRegistryServiceProvider(TypeRegistry())

    with pytest.raises(ServiceNotFoundError):
        provider.get(Logger)


def test_get_all_returns_every_matching_instance() -> None:
    provider = TypeRegistryServiceProvider(build_registry())

    handlers = provider.get_all(object)

    assert len(handlers) == 3  # the logger and both handlers


def test_has_reflects_what_was_registered() -> None:
    provider = TypeRegistryServiceProvider(build_registry())

    assert provider.has(AddHandler)
    assert not provider.has(str)


def test_get_all_types_lists_every_registered_type() -> None:
    provider = TypeRegistryServiceProvider(build_registry())

    assert set(provider.get_all_types()) == {Logger, AddHandler, MultiplyHandler}


def test_len_counts_every_registered_instance() -> None:
    provider = TypeRegistryServiceProvider(build_registry())

    assert len(provider) == 3


# ---- The money shot: swap the provider, not the call site ----


async def test_request_resolves_through_the_custom_provider() -> None:
    mediator = build_mediator()

    result = await mediator.send(Add(a=2, b=3))

    assert result == 5


async def test_same_call_site_works_with_either_provider() -> None:
    logger = Logger()

    custom_mediator = Mediator(TypeRegistryServiceProvider(build_registry(logger)))

    services = Services()
    services.add(AddHandler(logger))
    hand_wired_mediator = Mediator(services.provider())

    # Identical request, identical call site, two completely different ServiceProvider
    # implementations underneath. The mediator never notices the difference.
    custom_result = await custom_mediator.send(Add(a=10, b=20))
    hand_wired_result = await hand_wired_mediator.send(Add(a=10, b=20))

    assert custom_result == hand_wired_result == 30
