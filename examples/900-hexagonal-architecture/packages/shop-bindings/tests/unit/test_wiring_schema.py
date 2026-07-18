"""Keep runtime validation and VS Code diagnostics aligned."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from shop.bindings.settings import ConfigurationError
from shop.bindings.wiring import load_manifest

type ManifestDocument = dict[str, Any]


def _add_invalid_provider_name(document: ManifestDocument) -> None:
    document["providers"]["NotSnakeCase"] = {"impl": "builtins.object"}


def _add_unknown_role(document: ManifestDocument) -> None:
    document["bindings"]["worker"] = {"providers": {}}


def _duplicate_role_resource(document: ManifestDocument) -> None:
    document["bindings"]["application"]["resources"] = ["database", "database"]


def _add_unsupported_argument_mapping(document: ManifestDocument) -> None:
    document["providers"]["clock"]["arguments"] = {"settings": {"unsupported": "mapping"}}


def _add_lifetime_to_provider_alias(document: ManifestDocument) -> None:
    document["providers"]["database_alias"] = {
        "$ref": "database",
        "lifetime": "singleton",
    }


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    return json.loads(Path("configuration.schema.json").read_text())


@pytest.fixture(scope="module")
def validator(schema: dict[str, object]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "manifest_path",
    sorted(Path("configuration").glob("*.yaml")),
)
def test_checked_in_manifest_satisfies_editor_and_runtime_schemas(
    validator: Draft202012Validator,
    manifest_path: Path,
) -> None:
    # Arrange
    document = yaml.safe_load(manifest_path.read_text())

    # Act
    schema_errors = list(validator.iter_errors(document))
    manifest = load_manifest(manifest_path)

    # Assert
    assert schema_errors == []
    assert manifest.providers


def test_schema_reports_a_missing_application_provider(
    validator: Draft202012Validator,
) -> None:
    # Arrange
    manifest = yaml.safe_load(Path("configuration/default.yaml").read_text())
    del manifest["bindings"]["application"]["providers"]["storage"]

    # Act
    errors = list(validator.iter_errors(manifest))

    # Assert
    assert any(
        error.validator == "required" and "'storage' is a required property" in error.message
        for error in errors
    )


def test_schema_reports_a_missing_relay_provider(
    validator: Draft202012Validator,
) -> None:
    # Arrange
    manifest = yaml.safe_load(Path("configuration/default.yaml").read_text())
    del manifest["bindings"]["relay"]["providers"]["publisher"]

    # Act
    errors = list(validator.iter_errors(manifest))

    # Assert
    assert any(
        error.validator == "required" and "'publisher' is a required property" in error.message
        for error in errors
    )


def test_schema_reports_a_missing_provider_implementation(
    validator: Draft202012Validator,
) -> None:
    # Arrange
    manifest = yaml.safe_load(Path("configuration/default.yaml").read_text())
    manifest["providers"]["clock"] = {}

    # Act
    errors = list(validator.iter_errors(manifest))

    # Assert
    assert any(error.validator == "oneOf" for error in errors)


@pytest.mark.parametrize(
    ("mutate", "expected_validator"),
    [
        (_add_invalid_provider_name, "pattern"),
        (_add_unknown_role, "additionalProperties"),
        (_duplicate_role_resource, "uniqueItems"),
        (_add_unsupported_argument_mapping, "oneOf"),
        (_add_lifetime_to_provider_alias, "oneOf"),
    ],
)
def test_editor_and_runtime_reject_the_same_structural_errors(
    tmp_path: Path,
    validator: Draft202012Validator,
    mutate: Callable[[ManifestDocument], None],
    expected_validator: str,
) -> None:
    # Arrange
    document = yaml.safe_load(Path("configuration/default.yaml").read_text())
    mutate(document)
    path = tmp_path / "configuration.yaml"
    path.write_text(yaml.safe_dump(document))

    # Act
    schema_errors = list(validator.iter_errors(document))
    with pytest.raises(ConfigurationError) as runtime_error:
        load_manifest(path)

    # Assert
    assert any(error.validator == expected_validator for error in schema_errors)
    assert "wiring manifest" in str(runtime_error.value)


def test_schema_describes_every_reader_facing_composition_layer(
    schema: dict[str, object],
) -> None:
    # Arrange
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    expected_definitions = {
        "provider",
        "implementationProvider",
        "argument",
        "environmentReference",
        "roleResources",
        "applicationRole",
        "relayRole",
        "consumerRole",
    }

    # Act
    descriptions = {
        name: definition.get("description")
        for name, definition in definitions.items()
        if name in expected_definitions and isinstance(definition, dict)
    }

    # Assert
    assert set(descriptions) == expected_definitions
    assert all(
        isinstance(description, str) and description for description in descriptions.values()
    )


def test_vscode_associates_deployment_yaml_with_the_configuration_schema() -> None:
    # Arrange
    settings_path = Path(".vscode/settings.json")

    # Act
    settings = json.loads(settings_path.read_text())

    # Assert
    assert settings["yaml.schemas"]["./configuration.schema.json"] == ["configuration/*.yaml"]
