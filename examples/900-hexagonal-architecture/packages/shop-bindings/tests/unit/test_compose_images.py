"""Keep Compose deployment inputs centralized, immutable, and role-correct."""

import json
import re
from pathlib import Path

import yaml

IMAGE_INPUT_FILES = (
    Path("compose.yaml"),
    Path("compose.aws.yaml"),
    Path("compose.azure.yaml"),
    Path("docker/Dockerfile"),
)
IMAGE_ENVIRONMENT_FILE = Path(".env.images")
LOCAL_BUILD_OUTPUTS = {
    "SHOP_AWS_ADMINISTRATION_IMAGE",
    "SHOP_AWS_OPENAPI_IMAGE",
    "SHOP_AWS_WORKER_IMAGE",
    "SHOP_AZURE_ADMINISTRATION_IMAGE",
    "SHOP_AZURE_OPENAPI_IMAGE",
    "SHOP_AZURE_WORKER_IMAGE",
}


def image_environment() -> dict[str, str]:
    return {
        name: value
        for line in IMAGE_ENVIRONMENT_FILE.read_text().splitlines()
        if line and not line.startswith("#")
        for name, value in [line.split("=", 1)]
        if name.endswith("_IMAGE")
    }


def test_compose_image_names_are_declared_in_image_environment() -> None:
    # Arrange
    environment = image_environment()
    referenced: set[str] = set()
    literal_image_files: list[Path] = []

    # Act
    for image_input_file in IMAGE_INPUT_FILES:
        document = image_input_file.read_text()
        referenced.update(re.findall(r"^\s*image: \$\{([A-Z0-9_]+)\}$", document, re.MULTILINE))
        referenced.update(
            re.findall(
                r"^\s*FROM \$\{([A-Z0-9_]+)\}(?:\s+AS\s+[a-z0-9_-]+)?$",
                document,
                re.IGNORECASE | re.MULTILINE,
            )
        )
        if re.search(r"^\s*image: (?!\$\{)", document, re.MULTILINE):
            literal_image_files.append(image_input_file)

    # Assert
    assert literal_image_files == []
    assert referenced == set(environment)


def test_external_images_have_immutable_sha256_digests() -> None:
    # Arrange
    expected_digest = r"[^@]+@sha256:[0-9a-f]{64}"

    # Act
    images = image_environment()

    # Assert
    for name, image in images.items():
        if name in LOCAL_BUILD_OUTPUTS:
            assert image.startswith("shop:")
        else:
            assert re.fullmatch(expected_digest, image), name


def test_collector_is_bounded_and_processes_memory_before_batches() -> None:
    # Arrange
    compose = yaml.safe_load(Path("compose.yaml").read_text())
    configuration = yaml.safe_load(Path("docker/opentelemetry/collector.yaml").read_text())

    # Act
    collector = compose["services"]["otel-collector"]
    pipelines = configuration["service"]["pipelines"]

    # Assert
    assert collector["mem_limit"] == "256m"
    assert collector["environment"]["GOMEMLIMIT"] == "160MiB"
    assert collector["read_only"] is True
    assert collector["cap_drop"] == ["ALL"]
    assert configuration["processors"]["memory_limiter"] == {
        "check_interval": "1s",
        "limit_percentage": 80,
        "spike_limit_percentage": 15,
    }
    assert pipelines["traces"]["processors"] == ["memory_limiter", "batch"]
    assert pipelines["metrics"]["processors"] == ["memory_limiter", "batch"]
    assert configuration["service"]["extensions"] == ["health_check"]


def test_compose_hardcodes_telemetry_by_process_role() -> None:
    # Arrange
    image_environment_file = IMAGE_ENVIRONMENT_FILE.read_text()
    compose = yaml.safe_load(Path("compose.yaml").read_text())
    services = compose["services"]

    # Act
    observed = {
        name: service["environment"]
        for name, service in services.items()
        if name.startswith("shop-")
    }

    # Assert
    assert "OTEL_SDK_DISABLED=" not in image_environment_file
    assert "OTEL_EXPORTER_OTLP_ENDPOINT=" not in image_environment_file
    assert observed["shop-openapi"]["OTEL_SDK_DISABLED"] == "false"
    assert observed["shop-relay"]["OTEL_SDK_DISABLED"] == "false"
    assert observed["shop-worker"]["OTEL_SDK_DISABLED"] == "false"
    assert observed["shop-administration"]["OTEL_SDK_DISABLED"] == "false"
    assert {environment["OTEL_EXPORTER_OTLP_ENDPOINT"] for environment in observed.values()} == {
        "http://otel-collector:4317"
    }


def test_each_instrumented_process_waits_for_the_collector() -> None:
    # Arrange
    compose = yaml.safe_load(Path("compose.yaml").read_text())

    # Act
    shop_services = {
        name: service for name, service in compose["services"].items() if name.startswith("shop-")
    }

    # Assert
    for service in shop_services.values():
        assert service["depends_on"]["otel-collector"] == {"condition": "service_started"}


def test_each_cloud_builds_a_cli_only_administration_image() -> None:
    # Arrange
    deployments = {
        "compose.aws.yaml": "${SHOP_AWS_ADMINISTRATION_IMAGE}",
        "compose.azure.yaml": "${SHOP_AZURE_ADMINISTRATION_IMAGE}",
    }

    # Act
    observed = {
        path: yaml.safe_load(Path(path).read_text())["services"]["shop-administration"]
        for path in deployments
    }

    # Assert
    for path, image in deployments.items():
        service = observed[path]
        assert service["image"] == image
        assert service["build"]["args"]["SHOP_HOST"] == "cli"


def test_each_cloud_identifies_telemetry_with_standard_resource_attributes() -> None:
    # Arrange
    deployments = {
        "compose.aws.yaml": "local-aws",
        "compose.azure.yaml": "local-azure",
    }

    # Act
    observed = {path: yaml.safe_load(Path(path).read_text())["services"] for path in deployments}

    # Assert
    for path, environment_name in deployments.items():
        services = observed[path]
        for name in (
            "shop-openapi",
            "shop-relay",
            "shop-worker",
            "shop-administration",
        ):
            attributes = services[name]["environment"]["OTEL_RESOURCE_ATTRIBUTES"]
            assert "service.namespace=shop" in attributes
            assert f"deployment.environment.name={environment_name}" in attributes


def test_relay_startup_does_not_wait_for_unrelated_object_storage() -> None:
    # Arrange
    deployments = {
        "compose.aws.yaml": "minio-init",
        "compose.azure.yaml": "azurite-init",
    }

    # Act
    dependencies = {
        path: yaml.safe_load(Path(path).read_text())["services"]["shop-relay"]["depends_on"]
        for path in deployments
    }

    # Assert
    for path, storage_initializer in deployments.items():
        assert storage_initializer not in dependencies[path]


def test_all_brokers_use_the_documented_five_attempt_dead_letter_threshold() -> None:
    # Arrange
    default = yaml.safe_load(Path("configuration/default.yaml").read_text())
    aws = yaml.safe_load(Path("compose.aws.yaml").read_text())
    azure = json.loads(Path("docker/azure/servicebus-emulator.json").read_text())

    # Act
    default_threshold = default["providers"]["broker"]["arguments"]["max_delivery_count"]
    aws_command = aws["services"]["sqs-init"]["command"][0]
    azure_threshold = azure["UserConfig"]["Namespaces"][0]["Queues"][0]["Properties"][
        "MaxDeliveryCount"
    ]

    # Assert
    assert default_threshold == 5
    assert "--queue-name shop-events-dlq" in aws_command
    assert 'maxReceiveCount\\\\":\\\\"5' in aws_command
    assert azure_threshold == 5


def test_runtime_images_use_selected_extras_and_the_unified_configuration_path() -> None:
    # Arrange
    dockerfile = Path("docker/Dockerfile").read_text()
    compose = yaml.safe_load(Path("compose.yaml").read_text())
    cloud_compose = [
        yaml.safe_load(Path(path).read_text())
        for path in ("compose.aws.yaml", "compose.azure.yaml")
    ]
    shop_services = {
        name: service for name, service in compose["services"].items() if name.startswith("shop-")
    }
    configuration_copy = (
        "COPY --link examples/900-hexagonal-architecture/configuration/${SHOP_PROFILE}.yaml"
    )

    # Act
    wiring_paths = {service["environment"]["SHOP_WIRING"] for service in shop_services.values()}
    builds = [
        service["build"]
        for document in cloud_compose
        for name, service in document["services"].items()
        if name.startswith("shop-")
    ]

    # Assert
    assert '--extra "${SHOP_HOST}"' in dockerfile
    assert '--extra "${SHOP_PROFILE}"' in dockerfile
    assert configuration_copy in dockerfile
    assert "source=src,target=/workspace/src,readonly" in dockerfile
    assert wiring_paths == {"/etc/shop/configuration.yaml"}
    assert {build["context"] for build in builds} == {"../.."}
    assert {build["dockerfile"] for build in builds} == {
        "examples/900-hexagonal-architecture/docker/Dockerfile"
    }
    assert "ENTRYPOINT" not in dockerfile
    assert "CMD" not in dockerfile


def test_repository_build_context_exposes_only_required_source_inputs() -> None:
    # Arrange
    ignore_file = Path("docker/Dockerfile.dockerignore")

    # Act
    patterns = set(ignore_file.read_text().splitlines())

    # Assert
    assert "**" in patterns
    assert "!src/**" in patterns
    assert "!examples/900-hexagonal-architecture/packages/**" in patterns
    assert "!examples/900-hexagonal-architecture/configuration/*.yaml" in patterns
    assert not Path(".dockerignore").exists()


def test_compose_tasks_load_the_image_environment_file() -> None:
    # Arrange
    tasks = Path("tasks.compose.toml").read_text()

    # Act
    compose_commands = [
        line for line in tasks.splitlines() if line.startswith('cmd = "docker compose ')
    ]

    # Assert
    assert compose_commands
    assert all("docker compose --env-file .env.images " in line for line in compose_commands)
