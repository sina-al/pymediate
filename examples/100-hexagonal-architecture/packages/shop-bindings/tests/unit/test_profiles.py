"""Keep installation profiles aligned with their configuration manifests."""

import tomllib
from pathlib import Path

import yaml


def test_root_extras_keep_hosts_orthogonal_to_infrastructure() -> None:
    # Arrange
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]

    # Act
    extras = project["optional-dependencies"]

    # Assert
    assert extras["default"] == ["shop-bindings[default]"]
    assert extras["aws"] == ["shop-bindings[aws,observability]"]
    assert extras["azure"] == ["shop-bindings[azure,observability]"]
    assert extras["cli"] == ["shop-adapter-cli"]
    assert extras["openapi"] == ["shop-adapter-openapi"]
    assert extras["worker"] == ["shop-adapter-worker"]


def test_cloud_binding_profiles_include_shared_hypothetical_services() -> None:
    # Arrange
    path = Path("packages/shop-bindings/pyproject.toml")
    project = tomllib.loads(path.read_text())["project"]
    extras = project["optional-dependencies"]

    # Act
    dependencies = project["dependencies"]

    # Assert
    assert "shop-adapter-common" in dependencies
    assert "shop-adapter-weasyprint" in dependencies
    assert set(extras["aws"]) == {
        "shop-adapter-aws",
        "shop-adapter-ephemeral",
        "shop-adapter-postgres",
    }
    assert set(extras["azure"]) == {
        "shop-adapter-azure",
        "shop-adapter-ephemeral",
        "shop-adapter-postgres",
    }


def test_each_profile_installs_every_adapter_named_by_its_configuration() -> None:
    # Arrange
    bindings_project = tomllib.loads(Path("packages/shop-bindings/pyproject.toml").read_text())[
        "project"
    ]
    required = set(bindings_project["dependencies"])
    extras = bindings_project["optional-dependencies"]
    distribution_by_namespace = {
        "shop.adapters.aws": "shop-adapter-aws",
        "shop.adapters.azure": "shop-adapter-azure",
        "shop.adapters.common": "shop-adapter-common",
        "shop.adapters.ephemeral": "shop-adapter-ephemeral",
        "shop.adapters.postgres": "shop-adapter-postgres",
        "shop.adapters.weasyprint": "shop-adapter-weasyprint",
    }

    # Act
    missing_by_profile: dict[str, set[str]] = {}
    for profile in ("default", "aws", "azure"):
        installed = required | set(extras[profile])
        document = yaml.safe_load(Path(f"configuration/{profile}.yaml").read_text())
        implementations = {
            spec["impl"]
            for spec in document["providers"].values()
            if "impl" in spec and spec["impl"].startswith("shop.adapters.")
        }
        selected_distributions = {
            distribution
            for namespace, distribution in distribution_by_namespace.items()
            if any(implementation.startswith(f"{namespace}.") for implementation in implementations)
        }
        missing_by_profile[profile] = selected_distributions - installed

    # Assert
    assert missing_by_profile == {"default": set(), "aws": set(), "azure": set()}


def test_every_workspace_package_publishes_its_architecture_readme() -> None:
    # Arrange
    expected_packages = {
        "shop-adapter-aws",
        "shop-adapter-azure",
        "shop-adapter-cli",
        "shop-adapter-common",
        "shop-adapter-ephemeral",
        "shop-adapter-openapi",
        "shop-adapter-postgres",
        "shop-adapter-weasyprint",
        "shop-adapter-worker",
        "shop-application",
        "shop-bindings",
        "shop-domain",
        "shop-ports",
    }

    # Act
    packages = sorted(Path("packages").glob("*/pyproject.toml"))
    metadata = {
        path.parent.name: (
            tomllib.loads(path.read_text())["project"],
            path.with_name("README.md"),
        )
        for path in packages
    }

    # Assert
    assert set(metadata) == expected_packages
    for package_name, (project, readme) in metadata.items():
        assert project["readme"] == "README.md", package_name
        assert readme.is_file()
        content = readme.read_text()
        assert content.startswith("# Shop ")
        assert "../../README.md" in content


def test_application_distribution_publishes_one_owned_namespace() -> None:
    # Arrange
    path = Path("packages/shop-application/pyproject.toml")

    # Act
    document = tomllib.loads(path.read_text())

    # Assert
    assert document["project"]["name"] == "shop-application"
    assert document["tool"]["uv"]["build-backend"]["module-name"] == "shop.application"
