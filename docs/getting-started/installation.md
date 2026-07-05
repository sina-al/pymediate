# Installation

PyMediate is available on [PyPI](https://pypi.org/project/pymediate/) and installs with your favorite package manager.

## Requirements

- Python 3.12 or higher.
- No required dependencies for core functionality.
- Optional: `dependency-injector>=4.41.0` for dependency injection (DI) integration.

## Installation options

### Core package

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

### With dependency injection support

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

## Development installation

To contribute to PyMediate or run the tests:

```bash
# Clone the repository
git clone https://github.com/sina-al/pymediate.git
cd pymediate

# Install with dev dependencies using uv
uv sync --all-extras

# Or install in editable mode with pip
pip install -e '.[di,dev]'
```

## Verify installation

Verify PyMediate installed correctly:

```python
import pymediate

print(pymediate.__version__)
```

## Optional dependencies

### `DependencyInjectorServiceProvider`

`DependencyInjectorServiceProvider` is only available when you install PyMediate with the `[di]` extra. If you try to use it without installing `dependency-injector`, the import fails:

```python
from pymediate.providers import DependencyInjectorServiceProvider
# ModuleNotFoundError: No module named 'dependency_injector'
```

**Solution:** Install with the `[di]` extra:

```bash
pip install pymediate[di]
```

See the [troubleshooting guide](../advanced/troubleshooting.md#dependencyinjectorserviceprovider-not-available) for more details.

## Next steps

Now that PyMediate is installed, let's get started.

[Quick start →](quick-start.md){ .md-button .md-button--primary }
