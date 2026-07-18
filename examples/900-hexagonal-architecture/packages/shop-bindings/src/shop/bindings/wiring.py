"""Build executable roles from a declarative YAML provider manifest."""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import partial
from importlib import import_module
from inspect import isawaitable
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import yaml
from dependency_injector import containers, providers
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from shop.bindings.settings import ConfigurationError

_PROVIDER_NAME = r"^[a-z][a-z0-9_]*$"
_ARGUMENT_NAME = r"^[A-Za-z_]\w*$"
_ENVIRONMENT_NAME = r"^[A-Z_][A-Z0-9_]*$"

ProviderName = Annotated[str, StringConstraints(pattern=_PROVIDER_NAME)]
ArgumentName = Annotated[str, StringConstraints(pattern=_ARGUMENT_NAME)]


def _validate_literal(value: object) -> None:
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list):
        for item in value:
            _validate_literal(item)
        return
    raise ValueError("literal arguments must be null, a scalar, or a sequence of literal arguments")


def _validate_argument(value: object) -> None:
    if not isinstance(value, dict):
        _validate_literal(value)
        return

    keys = set(value)
    if keys == {"$ref"}:
        reference = value["$ref"]
        if not isinstance(reference, str) or re.fullmatch(_PROVIDER_NAME, reference) is None:
            raise ValueError("$ref must name a lowercase snake_case provider")
        return

    if keys in ({"env"}, {"env", "default"}):
        environment_name = value["env"]
        if (
            not isinstance(environment_name, str)
            or re.fullmatch(_ENVIRONMENT_NAME, environment_name) is None
        ):
            raise ValueError("env must name an uppercase environment variable")
        if "default" in value:
            _validate_literal(value["default"])
        return

    raise ValueError(
        "argument mappings must be exactly {$ref: provider_name} or "
        "{env: VARIABLE[, default: value]}"
    )


class ProviderSpec(BaseModel):
    """One named provider selected by a deployment manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    impl: str | None = Field(default=None, pattern=r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")
    ref: ProviderName | None = Field(default=None, alias="$ref")
    lifetime: Literal["singleton", "factory", "resource"] = "singleton"
    arguments: dict[ArgumentName, object] = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def validates_argument_shapes(
        cls, arguments: dict[ArgumentName, object]
    ) -> dict[ArgumentName, object]:
        for value in arguments.values():
            _validate_argument(value)
        return arguments

    @model_validator(mode="after")
    def selects_exactly_one_provider_style(self) -> ProviderSpec:
        if (self.impl is None) == (self.ref is None):
            raise ValueError("provide exactly one of impl or $ref")
        if self.ref is not None and self.model_fields_set & {"lifetime", "arguments"}:
            raise ValueError("a $ref cannot declare lifetime or arguments")
        return self


class ApplicationProviderBindings(BaseModel):
    """Providers required by the application container."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database: ProviderName
    unit: ProviderName
    catalogue: ProviderName
    storage: ProviderName
    clock: ProviderName
    inventory: ProviderName
    payments: ProviderName
    mailer: ProviderName
    rates: ProviderName
    renderer: ProviderName


class RelayProviderBindings(BaseModel):
    """Providers required by the outbox relay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox: ProviderName
    publisher: ProviderName


class ConsumerProviderBindings(BaseModel):
    """Providers required by the queue consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queue: ProviderName
    inbox: ProviderName


class RoleSpec(BaseModel):
    """Shared process-resource selection for one executable role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resources: list[ProviderName] = Field(default_factory=list)

    @field_validator("resources")
    @classmethod
    def resources_are_unique(cls, resources: list[ProviderName]) -> list[ProviderName]:
        if len(resources) != len(set(resources)):
            raise ValueError("resource names must be unique within a role")
        return resources


class ApplicationRoleSpec(RoleSpec):
    """Application providers and explicitly activated process resources."""

    providers: ApplicationProviderBindings


class RelayRoleSpec(RoleSpec):
    """Relay providers and explicitly activated process resources."""

    providers: RelayProviderBindings


class ConsumerRoleSpec(RoleSpec):
    """Consumer providers and explicitly activated process resources."""

    providers: ConsumerProviderBindings


class RoleBindings(BaseModel):
    """Composition required by each independently executable role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    application: ApplicationRoleSpec
    relay: RelayRoleSpec | None = None
    consumer: ConsumerRoleSpec | None = None


class WiringManifest(BaseModel):
    """A complete deployment choice validated before composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    providers: dict[ProviderName, ProviderSpec] = Field(min_length=1)
    bindings: RoleBindings


class ProviderCollection:
    """Named Dependency Injector providers selected for one executable role."""

    def __init__(self, providers_by_name: dict[str, providers.Provider[Any]]) -> None:
        self.providers = providers_by_name


def _role_spec(
    bindings: RoleBindings,
    name: str,
) -> ApplicationRoleSpec | RelayRoleSpec | ConsumerRoleSpec:
    match name:
        case "application":
            return bindings.application
        case "relay" if bindings.relay is not None:
            return bindings.relay
        case "consumer" if bindings.consumer is not None:
            return bindings.consumer
        case _:
            raise ConfigurationError(
                f"Shop cannot start: wiring has no {name!r} bindings"
            ) from None


def _provider_bindings(
    role: ApplicationRoleSpec | RelayRoleSpec | ConsumerRoleSpec,
) -> dict[str, str]:
    return cast("dict[str, str]", role.providers.model_dump())


async def _await_if_needed(result: object) -> None:
    if isawaitable(result):
        await result


class Wiring:
    """Resolved provider graph with explicit role-scoped resource ownership."""

    def __init__(
        self,
        manifest: WiringManifest,
        providers_by_name: dict[str, providers.Provider[Any]],
    ) -> None:
        self._manifest = manifest
        self._providers = providers_by_name
        self._active = False
        self._validate_role_references()

    def _validate_role_references(self) -> None:
        for role_name in ("application", "relay", "consumer"):
            try:
                role = _role_spec(self._manifest.bindings, role_name)
            except ConfigurationError:
                continue
            for dependency, provider_name in _provider_bindings(role).items():
                if provider_name not in self._providers:
                    raise ConfigurationError(
                        "Shop cannot start: "
                        f"bindings.{role_name}.providers.{dependency} references unknown provider "
                        f"{provider_name!r}"
                    )
            for index, provider_name in enumerate(role.resources):
                provider = self._providers.get(provider_name)
                if provider is None:
                    raise ConfigurationError(
                        "Shop cannot start: "
                        f"bindings.{role_name}.resources.{index} references unknown provider "
                        f"{provider_name!r}"
                    )
                if not isinstance(provider, providers.Resource):
                    raise ConfigurationError(
                        "Shop cannot start: "
                        f"bindings.{role_name}.resources.{index} references provider "
                        f"{provider_name!r}, whose lifetime is not resource"
                    )

    def role(self, name: str, expected: set[str]) -> ProviderCollection:
        """Select and validate providers injected into one executable component."""
        role = _role_spec(self._manifest.bindings, name)
        bindings = _provider_bindings(role)
        actual = set(bindings)
        missing, unknown = expected - actual, actual - expected
        if missing or unknown:
            problems = []
            if missing:
                problems.append(f"missing bindings: {', '.join(sorted(missing))}")
            if unknown:
                problems.append(f"unknown bindings: {', '.join(sorted(unknown))}")
            raise ConfigurationError(f"Shop cannot start: {name} wiring has " + "; ".join(problems))
        return ProviderCollection(
            {
                dependency: self._providers[provider_name]
                for dependency, provider_name in bindings.items()
            }
        )

    def _provider_graph_for(self, role_names: Iterable[str]) -> list[providers.Provider[Any]]:
        selected: dict[int, providers.Provider[Any]] = {}
        for role_name in role_names:
            role = _role_spec(self._manifest.bindings, role_name)
            provider_names = [*_provider_bindings(role).values(), *role.resources]
            for provider_name in provider_names:
                provider = self._providers[provider_name]
                selected[id(provider)] = provider
                for dependency in provider.traverse():
                    selected[id(dependency)] = dependency
        return list(selected.values())

    @staticmethod
    def _restore_async_modes(
        provider_graph: Iterable[providers.Provider[Any]],
        modes: Mapping[int, Literal["enabled", "disabled", "undefined"]],
    ) -> None:
        for provider in provider_graph:
            match modes[id(provider)]:
                case "enabled":
                    provider.enable_async_mode()
                case "disabled":
                    provider.disable_async_mode()
                case "undefined":
                    provider.reset_async_mode()

    @staticmethod
    def _async_modes(
        provider_graph: Iterable[providers.Provider[Any]],
    ) -> dict[int, Literal["enabled", "disabled", "undefined"]]:
        modes: dict[int, Literal["enabled", "disabled", "undefined"]] = {}
        for provider in provider_graph:
            if provider.is_async_mode_enabled():
                modes[id(provider)] = "enabled"
            elif provider.is_async_mode_disabled():
                modes[id(provider)] = "disabled"
            else:
                modes[id(provider)] = "undefined"
        return modes

    @staticmethod
    def _resource_providers(
        provider_graph: Iterable[providers.Provider[Any]],
    ) -> dict[str, providers.Resource[Any]]:
        selected = {
            id(provider): provider
            for provider in provider_graph
            if isinstance(provider, providers.Resource)
        }
        return {
            f"selected_resource_{index}": resource
            for index, resource in enumerate(selected.values())
        }

    @asynccontextmanager
    async def activate(self, *role_names: str) -> AsyncIterator[Wiring]:
        """Initialize only resources owned or injected by the selected roles."""
        if not role_names:
            raise ConfigurationError("Shop cannot start: activate at least one wiring role")
        if self._active:
            raise ConfigurationError("Shop cannot start: this wiring is already active")

        provider_graph = self._provider_graph_for(dict.fromkeys(role_names))
        lifecycle_providers = self._resource_providers(provider_graph)
        original_async_modes = self._async_modes(provider_graph)
        lifecycle = containers.DynamicContainer()
        lifecycle.set_providers(**lifecycle_providers)
        self._active = True
        try:
            try:
                await _await_if_needed(lifecycle.init_resources())
                for provider in provider_graph:
                    provider.disable_async_mode()
            except BaseException as startup_error:
                try:
                    for resource in lifecycle_providers.values():
                        resource.enable_async_mode()
                    await _await_if_needed(lifecycle.shutdown_resources())
                except BaseException as cleanup_error:
                    raise BaseExceptionGroup(
                        "Shop resource startup and cleanup both failed",
                        [startup_error, cleanup_error],
                    ) from None
                finally:
                    self._restore_async_modes(provider_graph, original_async_modes)
                raise

            try:
                yield self
            finally:
                try:
                    for resource in lifecycle_providers.values():
                        resource.enable_async_mode()
                    await _await_if_needed(lifecycle.shutdown_resources())
                finally:
                    self._restore_async_modes(provider_graph, original_async_modes)
        finally:
            self._active = False


def _format_manifest_error(path: Path, error: ValidationError) -> ConfigurationError:
    lines = [f"Shop cannot start because wiring manifest {path} is invalid:"]
    for issue in error.errors(include_url=False):
        location = ".".join(str(part) for part in issue["loc"])
        lines.append(f"  - {location}: {issue['msg']}")
    return ConfigurationError("\n".join(lines))


def load_manifest(path: Path) -> WiringManifest:
    """Read and validate YAML without importing any concrete implementation."""
    try:
        document = yaml.safe_load(path.read_text())
    except OSError as error:
        raise ConfigurationError(
            f"Shop cannot start: cannot read wiring manifest {path}: {error}"
        ) from None
    except yaml.YAMLError as error:
        raise ConfigurationError(
            f"Shop cannot start: cannot parse wiring manifest {path}: {error}"
        ) from None

    try:
        return WiringManifest.model_validate(document)
    except ValidationError as error:
        raise _format_manifest_error(path, error) from None


def _import_implementation(path: str) -> Callable[..., object]:
    module_name, _, attribute_name = path.rpartition(".")
    try:
        implementation = getattr(import_module(module_name), attribute_name)
    except (AttributeError, ImportError) as error:
        raise ConfigurationError(
            f"Shop cannot start: provider implementation {path!r} cannot be imported: {error}"
        ) from None
    if not callable(implementation):
        raise ConfigurationError(
            f"Shop cannot start: provider implementation {path!r} is not callable"
        )
    return cast("Callable[..., object]", implementation)


def _resolve_argument(
    value: object, resolve_provider: Callable[[str], providers.Provider[Any]]
) -> object:
    if not isinstance(value, dict):
        return value
    keys = set(value)
    if keys == {"$ref"}:
        return resolve_provider(cast("str", value["$ref"]))
    if keys in ({"env"}, {"env", "default"}):
        environment_name = cast("str", value["env"])
        environment_value = os.getenv(environment_name)
        if environment_value is not None and environment_value != "":
            return environment_value
        if "default" in value:
            return value["default"]
        raise ConfigurationError(
            "Shop cannot start because its configuration is invalid:\n"
            f"  - {environment_name}: Field required"
        )
    raise AssertionError("ProviderSpec validation should reject unsupported argument mappings")


@asynccontextmanager
async def _manage_resource(
    implementation: Callable[..., object],
    **arguments: object,
) -> AsyncIterator[Any]:
    manager = cast("AbstractAsyncContextManager[Any]", implementation(**arguments))
    async with manager as resource:
        yield resource


def create_wiring(path: Path) -> Wiring:
    """Resolve the complete named provider graph without activating a role."""
    manifest = load_manifest(path)
    selected: dict[str, providers.Provider[Any]] = {}
    resolving: list[str] = []

    def resolve(name: str) -> providers.Provider[Any]:
        if name in selected:
            return selected[name]
        try:
            spec = manifest.providers[name]
        except KeyError:
            location = " -> ".join([*resolving, name])
            raise ConfigurationError(
                f"Shop cannot start: unknown provider reference {name!r} at {location}"
            ) from None
        if name in resolving:
            cycle = " -> ".join([*resolving[resolving.index(name) :], name])
            raise ConfigurationError(f"Shop cannot start: provider reference cycle: {cycle}")

        resolving.append(name)
        try:
            if spec.ref is not None:
                provider = resolve(spec.ref)
            else:
                arguments = {
                    argument_name: _resolve_argument(argument, resolve)
                    for argument_name, argument in spec.arguments.items()
                }
                assert spec.impl is not None
                implementation = _import_implementation(spec.impl)
                match spec.lifetime:
                    case "resource":
                        provider = providers.Resource(
                            partial(_manage_resource, implementation),
                            **arguments,
                        )
                    case "factory":
                        provider = providers.Factory(cast("Any", implementation), **arguments)
                    case "singleton":
                        provider = providers.Singleton(cast("Any", implementation), **arguments)
        finally:
            resolving.pop()

        selected[name] = provider
        return provider

    for provider_name in manifest.providers:
        resolve(provider_name)

    return Wiring(manifest, selected)
