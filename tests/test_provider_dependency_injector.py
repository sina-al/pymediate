"""Focused tests for the optional Dependency Injector service provider."""

from dataclasses import dataclass
from typing import Any, assert_type, cast

import pytest
from dependency_injector import containers, providers

from pymediate import Mediator, Notification, NotificationHandler, Request, RequestHandler
from pymediate.providers import DependencyInjectorServiceProvider
from pymediate.sync import Mediator as SyncMediator
from pymediate.sync import NotificationHandler as SyncNotificationHandler
from pymediate.sync import Request as SyncRequest
from pymediate.sync import RequestHandler as SyncRequestHandler


class Service:
    """Base service used across the discovery tests."""


class FirstService(Service):
    """First nested service."""


class SecondService(Service):
    """Direct service between two nested containers."""


class ThirdService(Service):
    """Last nested service."""


def test_nested_container_services_are_all_discovered() -> None:
    """Services declared in nested containers are all indexed via ``traverse()``."""

    class FirstContainer(containers.DeclarativeContainer):
        first = providers.Factory(FirstService)

    class ThirdContainer(containers.DeclarativeContainer):
        third = providers.Factory(ThirdService)

    class RootContainer(containers.DeclarativeContainer):
        first = providers.Container(FirstContainer)
        second = providers.Factory(SecondService)
        third = providers.Container(ThirdContainer)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert services.has(FirstService)
    assert services.has(SecondService)
    assert services.has(ThirdService)
    assert isinstance(services.get(FirstService), FirstService)
    assert isinstance(services.get(SecondService), SecondService)
    assert isinstance(services.get(ThirdService), ThirdService)


def test_injection_only_provider_is_indexed_via_traverse() -> None:
    """A provider reachable only through injection is indexed.

    ``traverse()`` walks the whole provider graph, so a provider used solely as an
    injected dependency - never declared as a container attribute - is discovered
    and resolvable like any other service.
    """

    class Hidden:
        pass

    class Repo(Service):
        def __init__(self, hidden: Hidden) -> None:
            self.hidden = hidden

    hidden_provider = providers.Singleton(Hidden)

    class RootContainer(containers.DeclarativeContainer):
        repo = providers.Factory(Repo, hidden=hidden_provider)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert services.has(Repo)
    assert services.has(Hidden)
    assert len(services) == 2
    assert isinstance(services.get(Hidden), Hidden)


def test_indexing_does_not_resolve_factories_or_unrelated_services() -> None:
    """Discovery and inheritance filtering do not create unused services."""
    constructed: list[str] = []

    class UsedService(Service):
        def __init__(self) -> None:
            constructed.append("used")

    class UnrelatedService:
        def __init__(self) -> None:
            constructed.append("unrelated")

    class RootContainer(containers.DeclarativeContainer):
        unrelated = providers.Factory(UnrelatedService)
        used = providers.Factory(UsedService)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert constructed == []

    assert isinstance(services.get(UsedService), UsedService)
    assert constructed == ["used"]


def test_annotated_factory_is_indexed_without_being_resolved() -> None:
    """A concrete factory return annotation supplies its service type."""
    constructed = 0

    def build_service() -> FirstService:
        nonlocal constructed
        constructed += 1
        return FirstService()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Factory(build_service)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert constructed == 0
    assert isinstance(services.get(FirstService), FirstService)
    assert constructed == 1


def test_opaque_factory_is_skipped_without_being_called() -> None:
    """An unannotated factory is skipped, not resolved to learn its type."""
    constructed = 0

    def build_service() -> Any:
        nonlocal constructed
        constructed += 1
        return FirstService()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Factory(build_service)

    services = DependencyInjectorServiceProvider(RootContainer())

    # The factory could not be typed without resolving it, so it never became a
    # service - and it was not called to find out.
    assert not services.has(FirstService)
    assert len(services) == 0
    assert constructed == 0


def test_bound_child_dependency_placeholder_is_skipped() -> None:
    """A ``providers.Dependency`` placeholder is composition-only, not a service.

    The root ``Singleton`` that binds it is a real declared service; the child's
    ``Dependency`` placeholder is skipped.
    """

    class Database:
        pass

    class Handler(Service):
        def __init__(self, database: Database) -> None:
            self.database = database

    class FeatureContainer(containers.DeclarativeContainer):
        database = providers.Dependency(instance_of=Database)
        handler = providers.Factory(Handler, database=database)

    class RootContainer(containers.DeclarativeContainer):
        database = providers.Singleton(Database)
        feature = providers.Container(FeatureContainer, database=database)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert services.has(Database)
    assert services.has(Handler)
    assert len(services) == 2


def test_object_and_collection_providers_have_intrinsic_types() -> None:
    """Providers with an intrinsic result type need no resolution or annotation."""
    instance = FirstService()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Object(instance)
        items = providers.List(1, 2)
        values = providers.Dict(answer=42)

    services = DependencyInjectorServiceProvider(RootContainer())

    service = services.get(FirstService)

    assert_type(service, FirstService)
    assert service is instance
    assert services.get(list) == [1, 2]
    assert services.get(dict) == {"answer": 42}


def test_opaque_selector_is_skipped() -> None:
    """A dynamic ``Selector`` cannot be typed without resolving it, so it is skipped."""

    class RootContainer(containers.DeclarativeContainer):
        selected = providers.Selector(
            lambda: "first",
            first=providers.Factory(FirstService),
        )

    services = DependencyInjectorServiceProvider(RootContainer())

    # The Selector itself is not indexed; its class-backed branch still is.
    assert services.has(FirstService)


def test_type_changing_override_is_seen_after_rebuilding_the_index() -> None:
    """Effective overrides define a new provider's construction-time type snapshot."""

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Factory(FirstService)

    container = RootContainer()
    original_services = DependencyInjectorServiceProvider(container)

    container.service.override(providers.Factory(SecondService))
    overridden_services = DependencyInjectorServiceProvider(container)

    assert original_services.has(FirstService)
    assert not original_services.has(SecondService)
    assert overridden_services.has(SecondService)
    assert isinstance(overridden_services.get(SecondService), SecondService)
    with pytest.raises(TypeError, match="rebuild.*type-changing override"):
        original_services.get(FirstService)


@pytest.mark.asyncio
async def test_asynchronous_provider_resolution_is_rejected() -> None:
    """The async mediator still needs synchronous construction from ServiceProvider."""

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Factory(FirstService)

    container = RootContainer()
    container.service.enable_async_mode()
    services = DependencyInjectorServiceProvider(container)

    with pytest.raises(TypeError, match="resolved asynchronously"):
        services.get(FirstService)


def test_coroutine_provider_is_skipped_during_indexing() -> None:
    """A coroutine provider cannot be a synchronous service source, so it is skipped."""

    async def build_service() -> FirstService:
        return FirstService()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Coroutine(build_service)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert not services.has(FirstService)
    assert len(services) == 0


@pytest.mark.asyncio
async def test_coroutine_result_is_closed_when_resolution_is_rejected() -> None:
    """A provider returning a raw coroutine is rejected without leaking it."""

    async def build_service() -> FirstService:
        return FirstService()

    coroutine = build_service()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Object(coroutine)

    services = DependencyInjectorServiceProvider(RootContainer())
    coroutine_type = cast("type[Any]", type(coroutine))

    with pytest.raises(TypeError, match="resolved asynchronously"):
        services.get(coroutine_type)

    assert cast(Any, coroutine).cr_frame is None


def test_resource_provider_is_skipped_without_initializing() -> None:
    """A resource provider is skipped and never started during indexing."""
    constructed = 0

    def build_service() -> FirstService:
        nonlocal constructed
        constructed += 1
        return FirstService()

    class RootContainer(containers.DeclarativeContainer):
        service = providers.Resource(build_service)

    services = DependencyInjectorServiceProvider(RootContainer())

    assert not services.has(FirstService)
    assert constructed == 0


def test_nested_container_cycle_is_handled_without_recursing() -> None:
    """``traverse()`` is cycle-safe, so a child-container cycle indexes without error."""
    root = containers.DynamicContainer()
    child = containers.DynamicContainer()
    root.set_provider(
        "child",
        providers.Container(containers.DynamicContainer, container=child),
    )
    child.set_provider(
        "root",
        providers.Container(containers.DynamicContainer, container=root),
    )

    services = DependencyInjectorServiceProvider(root)

    # No services are declared in either container, and the cycle does not recurse.
    assert len(services) == 0


def test_sync_mediator_can_be_composed_inside_the_scanned_container() -> None:
    """Dependency Injector's Self pattern does not recurse during service indexing."""

    @dataclass
    class SelfSyncResponse:
        value: int

    @dataclass
    class SelfSyncRequest(SyncRequest[SelfSyncResponse]):
        value: int

    class SelfSyncHandler(SyncRequestHandler[SelfSyncRequest]):
        def __init__(self, mediator: SyncMediator) -> None:
            self.mediator = mediator

        def __call__(self, request: SelfSyncRequest) -> SelfSyncResponse:
            return SelfSyncResponse(request.value)

    class RootContainer(containers.DeclarativeContainer):
        __self__ = providers.Self()
        services = providers.Singleton(DependencyInjectorServiceProvider, __self__)
        mediator = providers.Singleton(SyncMediator, services=services)
        handler = providers.Factory(SelfSyncHandler, mediator=mediator)

    container = RootContainer()

    mediator = container.mediator()
    response = mediator.send(SelfSyncRequest(value=42))

    assert response == SelfSyncResponse(value=42)
    assert container.services() is container.services()
    assert container.handler().mediator is mediator


@pytest.mark.asyncio
async def test_async_mediator_can_be_composed_inside_the_scanned_container() -> None:
    """Self composition works identically for the async mediator."""

    @dataclass
    class SelfAsyncResponse:
        value: int

    @dataclass
    class SelfAsyncRequest(Request[SelfAsyncResponse]):
        value: int

    class SelfAsyncHandler(RequestHandler[SelfAsyncRequest]):
        async def __call__(self, request: SelfAsyncRequest) -> SelfAsyncResponse:
            return SelfAsyncResponse(request.value)

    class RootContainer(containers.DeclarativeContainer):
        __self__ = providers.Self()
        handler = providers.Factory(SelfAsyncHandler)
        services = providers.Singleton(DependencyInjectorServiceProvider, __self__)
        mediator = providers.Singleton(Mediator, services=services)

    mediator = RootContainer().mediator()

    response = await mediator.send(SelfAsyncRequest(value=42))

    assert response == SelfAsyncResponse(value=42)


def test_nested_sync_handler_can_publish_through_the_injected_mediator() -> None:
    """A child-container handler can publish to other container-resolved handlers."""

    @dataclass
    class OrderPlaced(Notification):
        order_id: int

    @dataclass
    class PlaceOrderResponse:
        order_id: int

    @dataclass
    class PlaceOrderRequest(SyncRequest[PlaceOrderResponse]):
        order_id: int

    class PlaceOrderHandler(SyncRequestHandler[PlaceOrderRequest]):
        def __init__(self, mediator: SyncMediator) -> None:
            self._mediator = mediator

        def __call__(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
            self._mediator.publish(OrderPlaced(order_id=request.order_id))
            return PlaceOrderResponse(order_id=request.order_id)

    class RecordOrderPlaced(SyncNotificationHandler[OrderPlaced]):
        def __init__(self, notifications: list[OrderPlaced]) -> None:
            self._notifications = notifications

        def __call__(self, notification: OrderPlaced) -> None:
            self._notifications.append(notification)

    class OrdersContainer(containers.DeclarativeContainer):
        mediator = providers.Dependency(instance_of=SyncMediator)
        notifications = providers.Dependency(instance_of=list)

        place_order = providers.Factory(PlaceOrderHandler, mediator=mediator)
        record_order_placed = providers.Factory(
            RecordOrderPlaced,
            notifications=notifications,
        )

    class RootContainer(containers.DeclarativeContainer):
        __self__ = providers.Self()
        notifications: providers.Object[list[OrderPlaced]] = providers.Object([])
        services = providers.Singleton(DependencyInjectorServiceProvider, __self__)
        mediator = providers.Singleton(SyncMediator, services=services)
        orders = providers.Container(
            OrdersContainer,
            mediator=mediator,
            notifications=notifications,
        )

    # Arrange
    container = RootContainer()
    mediator = container.mediator()

    # Act
    response = mediator.send(PlaceOrderRequest(order_id=42))

    # Assert
    assert response == PlaceOrderResponse(order_id=42)
    assert container.notifications() == [OrderPlaced(order_id=42)]


@pytest.mark.asyncio
async def test_nested_async_handler_can_publish_through_the_injected_mediator() -> None:
    """The async mediator can close the same root-to-child notification loop."""

    @dataclass
    class RefundApproved(Notification):
        refund_id: int

    @dataclass
    class ApproveRefundResponse:
        refund_id: int

    @dataclass
    class ApproveRefundRequest(Request[ApproveRefundResponse]):
        refund_id: int

    class ApproveRefundHandler(RequestHandler[ApproveRefundRequest]):
        def __init__(self, mediator: Mediator) -> None:
            self._mediator = mediator

        async def __call__(
            self,
            request: ApproveRefundRequest,
        ) -> ApproveRefundResponse:
            await self._mediator.publish(RefundApproved(refund_id=request.refund_id))
            return ApproveRefundResponse(refund_id=request.refund_id)

    class RecordRefundApproval(NotificationHandler[RefundApproved]):
        def __init__(self, notifications: list[RefundApproved]) -> None:
            self._notifications = notifications

        async def __call__(self, notification: RefundApproved) -> None:
            self._notifications.append(notification)

    class RefundsContainer(containers.DeclarativeContainer):
        mediator = providers.Dependency(instance_of=Mediator)
        notifications = providers.Dependency(instance_of=list)

        approve_refund = providers.Factory(ApproveRefundHandler, mediator=mediator)
        record_refund_approval = providers.Factory(
            RecordRefundApproval,
            notifications=notifications,
        )

    class RootContainer(containers.DeclarativeContainer):
        __self__ = providers.Self()
        notifications: providers.Object[list[RefundApproved]] = providers.Object([])
        services = providers.Singleton(DependencyInjectorServiceProvider, __self__)
        mediator = providers.Singleton(Mediator, services=services)
        refunds = providers.Container(
            RefundsContainer,
            mediator=mediator,
            notifications=notifications,
        )

    # Arrange
    container = RootContainer()
    mediator = container.mediator()

    # Act
    response = await mediator.send(ApproveRefundRequest(refund_id=7))

    # Assert
    assert response == ApproveRefundResponse(refund_id=7)
    assert container.notifications() == [RefundApproved(refund_id=7)]
