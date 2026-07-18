"""Validate provider composition, role selection, and resource lifecycles."""

from __future__ import annotations

from collections.abc import Callable
from inspect import isawaitable
from pathlib import Path
from types import TracebackType
from typing import Self, cast

import pytest
import yaml
from dependency_injector import providers

import shop.bindings.wiring as wiring_module
from shop.adapters.ephemeral import SqliteDbGateway
from shop.application.orders.create_order import CreateOrderHandler
from shop.bindings.loading import application_context, load_container
from shop.bindings.settings import ConfigurationError
from shop.bindings.wiring import create_wiring, load_manifest

_APPLICATION_DEPENDENCIES = {
    "database",
    "unit",
    "catalogue",
    "storage",
    "clock",
    "inventory",
    "payments",
    "mailer",
    "rates",
    "renderer",
}


class ResourceProbe:
    """Record lifecycle calls made by a test wiring graph."""

    events: list[str] = []

    def __init__(
        self,
        name: str,
        dependency: object | None = None,
        fail_on_enter: bool = False,
    ) -> None:
        self._name = name
        self._dependency = dependency
        self._fail_on_enter = fail_on_enter

    async def __aenter__(self) -> Self:
        self.events.append(f"enter:{self._name}")
        if self._fail_on_enter:
            raise RuntimeError(f"cannot start {self._name}")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.events.append(f"exit:{self._name}")


@pytest.fixture
def probe_implementation(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    # Arrange
    original_import = wiring_module._import_implementation
    ResourceProbe.events = []

    def import_implementation(path: str) -> Callable[..., object]:
        if path == "tests.ResourceProbe":
            return ResourceProbe
        return original_import(path)

    # Act
    monkeypatch.setattr(wiring_module, "_import_implementation", import_implementation)

    # Assert
    assert ResourceProbe.events == []
    return ResourceProbe.events


def _application_providers(provider_name: str = "noop") -> dict[str, str]:
    return dict.fromkeys(_APPLICATION_DEPENDENCIES, provider_name)


def _write_manifest(
    tmp_path: Path,
    *,
    providers_document: dict[str, object] | None = None,
    application: dict[str, object] | None = None,
    relay: dict[str, object] | None = None,
    consumer: dict[str, object] | None = None,
) -> Path:
    providers_document = {"noop": {"impl": "builtins.object"}, **(providers_document or {})}
    bindings: dict[str, object] = {
        "application": application or {"providers": _application_providers(), "resources": []}
    }
    if relay is not None:
        bindings["relay"] = relay
    if consumer is not None:
        bindings["consumer"] = consumer
    path = tmp_path / "configuration.yaml"
    path.write_text(yaml.safe_dump({"providers": providers_document, "bindings": bindings}))
    return path


def test_build_only_helper_returns_an_unresolved_application_container() -> None:
    # Arrange
    path = Path("configuration/default.yaml")

    # Act
    container = load_container(path)

    # Assert
    assert container.mediator is not None


async def test_application_context_owns_the_default_database_lifecycle() -> None:
    # Arrange
    path = Path("configuration/default.yaml")

    # Act
    async with application_context(path) as container:
        database = cast("SqliteDbGateway", container.database())
        product = await container.catalogue().get_product("book")
        handle = container.orders.create_order()

    # Assert
    assert isinstance(database, SqliteDbGateway)
    assert product.sku == "book"
    assert isinstance(handle, CreateOrderHandler)
    assert not isawaitable(handle)
    assert database._connection is None


def test_missing_environment_value_is_rendered_for_container_logs(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "renderer": {
                "impl": "shop.adapters.weasyprint.renderer.WeasyPrintDocumentRenderer",
                "arguments": {"name": {"env": "SHOP_RENDERER_NAME"}},
            }
        },
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        create_wiring(path)

    # Assert
    assert str(error.value) == (
        "Shop cannot start because its configuration is invalid:\n"
        "  - SHOP_RENDERER_NAME: Field required"
    )


def test_role_reports_a_container_contract_mismatch(tmp_path: Path) -> None:
    # Arrange
    wiring = create_wiring(_write_manifest(tmp_path))

    # Act
    with pytest.raises(ConfigurationError) as error:
        wiring.role("application", set())

    # Assert
    assert "unknown bindings:" in str(error.value)
    assert "database" in str(error.value)


def test_missing_role_is_actionable(tmp_path: Path) -> None:
    # Arrange
    wiring = create_wiring(_write_manifest(tmp_path))

    # Act
    with pytest.raises(ConfigurationError) as error:
        wiring.role("relay", {"outbox", "publisher"})

    # Assert
    assert str(error.value) == "Shop cannot start: wiring has no 'relay' bindings"


def test_manifest_reports_an_invalid_provider_shape(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "configuration.yaml"
    path.write_text(
        "providers: {database: {$ref: database, arguments: {x: 1}}}\n"
        "bindings:\n"
        "  application:\n"
        "    providers:\n"
        + "".join(f"      {name}: database\n" for name in sorted(_APPLICATION_DEPENDENCIES))
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        load_manifest(path)

    # Assert
    assert "$ref cannot declare lifetime or arguments" in str(error.value)


def test_provider_references_are_order_independent(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "unit": {
                "impl": "builtins.dict",
                "lifetime": "factory",
                "arguments": {"database": {"$ref": "database"}},
            },
            "database": {"impl": "builtins.object"},
        },
        application={
            "providers": {
                **_application_providers(),
                "database": "database",
                "unit": "unit",
            }
        },
    )

    # Act
    wiring = create_wiring(path)
    selected = wiring.role("application", _APPLICATION_DEPENDENCIES).providers

    # Assert
    assert isinstance(selected["database"], providers.Singleton)
    assert isinstance(selected["unit"], providers.Factory)


def test_provider_reference_cycles_are_actionable(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={"first": {"$ref": "second"}, "second": {"$ref": "first"}},
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        create_wiring(path)

    # Assert
    assert "provider reference cycle: first -> second -> first" in str(error.value)


def test_unknown_role_provider_reference_has_its_configuration_path(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        application={"providers": {**_application_providers(), "database": "missing_database"}},
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        create_wiring(path)

    # Assert
    assert "bindings.application.providers.database" in str(error.value)
    assert "unknown provider 'missing_database'" in str(error.value)


def test_explicit_role_resource_must_have_resource_lifetime(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        application={"providers": _application_providers(), "resources": ["noop"]},
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        create_wiring(path)

    # Assert
    assert "bindings.application.resources.0" in str(error.value)
    assert "lifetime is not resource" in str(error.value)


def test_unknown_explicit_resource_has_its_configuration_path(tmp_path: Path) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        application={
            "providers": _application_providers(),
            "resources": ["missing_telemetry"],
        },
    )

    # Act
    with pytest.raises(ConfigurationError) as error:
        create_wiring(path)

    # Assert
    assert "bindings.application.resources.0" in str(error.value)
    assert "unknown provider 'missing_telemetry'" in str(error.value)


async def test_activation_discovers_injected_resources_and_keeps_factories_synchronous(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "database": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "database"},
            },
            "unit": {
                "impl": "builtins.dict",
                "lifetime": "factory",
                "arguments": {"database": {"$ref": "database"}},
            },
        },
        application={
            "providers": {
                **_application_providers(),
                "database": "database",
                "unit": "unit",
            }
        },
    )
    wiring = create_wiring(path)
    selected = wiring.role("application", _APPLICATION_DEPENDENCIES).providers

    # Act
    async with wiring.activate("application"):
        database = selected["database"]()
        unit = selected["unit"]()
        active_events = list(probe_implementation)

    # Assert
    assert isinstance(database, ResourceProbe)
    assert isinstance(unit, dict)
    assert unit == {"database": database}
    assert active_events == ["enter:database"]
    assert probe_implementation == ["enter:database", "exit:database"]


async def test_activation_is_scoped_to_selected_roles(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "application_resource": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "application"},
            },
            "relay_resource": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "relay"},
            },
        },
        application={
            "providers": _application_providers(),
            "resources": ["application_resource"],
        },
        relay={
            "providers": {"outbox": "noop", "publisher": "noop"},
            "resources": ["relay_resource"],
        },
    )
    wiring = create_wiring(path)

    # Act
    async with wiring.activate("relay"):
        active_events = list(probe_implementation)

    # Assert
    assert active_events == ["enter:relay"]
    assert probe_implementation == ["enter:relay", "exit:relay"]


async def test_multiple_roles_deduplicate_shared_resources(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "shared": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "shared"},
            }
        },
        application={
            "providers": {**_application_providers(), "database": "shared"},
            "resources": ["shared"],
        },
        consumer={
            "providers": {"queue": "noop", "inbox": "shared"},
            "resources": ["shared"],
        },
    )
    wiring = create_wiring(path)

    # Act
    async with wiring.activate("application", "consumer"):
        active_events = list(probe_implementation)

    # Assert
    assert active_events == ["enter:shared"]
    assert probe_implementation == ["enter:shared", "exit:shared"]


async def test_resource_dependencies_start_and_stop_in_dependency_order(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "database": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "database"},
            },
            "storage": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {
                    "name": "storage",
                    "dependency": {"$ref": "database"},
                },
            },
        },
        application={
            "providers": _application_providers(),
            "resources": ["storage"],
        },
    )
    wiring = create_wiring(path)

    # Act
    async with wiring.activate("application"):
        active_events = list(probe_implementation)

    # Assert
    assert active_events == ["enter:database", "enter:storage"]
    assert probe_implementation == [
        "enter:database",
        "enter:storage",
        "exit:storage",
        "exit:database",
    ]


async def test_startup_failure_closes_resources_that_already_started(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "healthy": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "healthy"},
            },
            "failing": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {
                    "name": "failing",
                    "dependency": {"$ref": "healthy"},
                    "fail_on_enter": True,
                },
            },
        },
        application={
            "providers": _application_providers(),
            "resources": ["failing"],
        },
    )
    wiring = create_wiring(path)

    # Act
    with pytest.raises(RuntimeError, match="cannot start failing"):
        async with wiring.activate("application"):
            pytest.fail("a failed resource must not enter the application body")

    # Assert
    assert probe_implementation == ["enter:healthy", "enter:failing", "exit:healthy"]


async def test_role_resources_close_when_executable_work_fails(
    tmp_path: Path,
    probe_implementation: list[str],
) -> None:
    # Arrange
    path = _write_manifest(
        tmp_path,
        providers_document={
            "database": {
                "impl": "tests.ResourceProbe",
                "lifetime": "resource",
                "arguments": {"name": "database"},
            }
        },
        application={"providers": {**_application_providers(), "database": "database"}},
    )
    wiring = create_wiring(path)

    # Act
    with pytest.raises(RuntimeError, match="application failed"):
        async with wiring.activate("application"):
            raise RuntimeError("application failed")

    # Assert
    assert probe_implementation == ["enter:database", "exit:database"]


async def test_nested_or_concurrent_activation_is_rejected(
    tmp_path: Path,
) -> None:
    # Arrange
    wiring = create_wiring(_write_manifest(tmp_path))

    # Act
    async with wiring.activate("application"):
        with pytest.raises(ConfigurationError) as error:
            async with wiring.activate("application"):
                pytest.fail("nested activation must not enter its body")

    # Assert
    assert str(error.value) == "Shop cannot start: this wiring is already active"


async def test_activation_requires_at_least_one_role(tmp_path: Path) -> None:
    # Arrange
    wiring = create_wiring(_write_manifest(tmp_path))

    # Act
    with pytest.raises(ConfigurationError) as error:
        async with wiring.activate():
            pytest.fail("empty activation must not enter its body")

    # Assert
    assert str(error.value) == "Shop cannot start: activate at least one wiring role"
