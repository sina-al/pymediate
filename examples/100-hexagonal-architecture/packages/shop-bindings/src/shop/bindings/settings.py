"""Validated bootstrap configuration for executable shop roles."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """An actionable startup configuration failure suitable for container logs."""


def _format_configuration_error(error: ValidationError, settings_type: type[BaseSettings]) -> str:
    prefix = str(settings_type.model_config.get("env_prefix", ""))
    problems = []
    for issue in error.errors(include_url=False):
        location = "_".join(str(part).upper() for part in issue["loc"])
        environment_name = f"{prefix}{location}"
        problems.append(f"  - {environment_name}: {issue['msg']}")
    return "Shop cannot start because its configuration is invalid:\n" + "\n".join(problems)


class BootstrapSettings(BaseSettings):
    """Select the declarative provider manifest before the app starts."""

    model_config = SettingsConfigDict(
        env_prefix="SHOP_",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    wiring: Path = Path("configuration/default.yaml")


def settings_from_environment[SettingsT: BaseSettings](
    settings_type: type[SettingsT],
) -> SettingsT:
    """Construct settings whose required fields are supplied by dynamic sources."""
    factory = cast("Callable[[], SettingsT]", settings_type)
    try:
        return factory()
    except ValidationError as error:
        raise ConfigurationError(_format_configuration_error(error, settings_type)) from None
