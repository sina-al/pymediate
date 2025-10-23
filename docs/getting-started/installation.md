# Installation

PyMediate is available on [PyPI](https://pypi.org/project/pymediate/) and can be installed with your favorite package manager.

## Requirements

- Python 3.12 or higher
- No required dependencies for core functionality
- Optional: `dependency-injector>=4.41.0` for DI integration

## Installation Options

### Core Package

Install just the core PyMediate package:

=== "pip"

    ```bash
    pip install pymediate
    ```

=== "uv"

    ```bash
    uv add pymediate
    ```

=== "poetry"

    ```bash
    poetry add pymediate
    ```

### With Dependency Injection Support

Install PyMediate with `dependency-injector` for DI container integration:

=== "pip"

    ```bash
    pip install pymediate[di]
    ```

=== "uv"

    ```bash
    uv add 'pymediate[di]'
    ```

=== "poetry"

    ```bash
    poetry add pymediate[di]
    ```

## Development Installation

If you want to contribute to PyMediate or run the tests:

```bash
# Clone the repository
git clone https://github.com/sina-al/pymediate.git
cd pymediate

# Install with dev dependencies using uv
uv sync --all-extras

# Or install in editable mode with pip
pip install -e '.[di,dev]'
```

## Verify Installation

Verify PyMediate is installed correctly:

```python
import pymediate

print(pymediate.__version__)
```

## Optional Dependencies

### DependencyInjectorServiceProvider

The `DependencyInjectorServiceProvider` is only available when you install PyMediate with the `[di]` extra. If you try to use it without installing the dependency-injector package, you'll get a helpful error message:

```python
from pymediate import DependencyInjectorServiceProvider

provider = DependencyInjectorServiceProvider(container)
# ImportError: DependencyInjectorServiceProvider requires the 'dependency-injector' package.
#
# To use DependencyInjectorServiceProvider, install PyMediate with the [di] extra:
#   pip install pymediate[di]
```

**Solution:** Install with the `[di]` extra:

```bash
pip install pymediate[di]
```

See the [Troubleshooting guide](../advanced/troubleshooting.md#dependencyinjectorserviceprovider-not-available) for more details.

## Next Steps

Now that PyMediate is installed, let's get started!

[Quick Start →](quick-start.md){ .md-button .md-button--primary }
