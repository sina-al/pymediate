# PyMediate Task Guide

This guide explains all available Poe the Poet tasks for PyMediate development.

## Quick Reference

```bash
poe              # Show all available tasks
poe test         # Run tests
poe lint         # Check code quality
poe format       # Format code
poe docs:serve   # Start documentation server
```

## Testing Tasks

| Command | Description |
|---------|-------------|
| `poe test` | Run all tests |
| `poe test:cov` | Run tests with coverage report (HTML + terminal) |
| `poe test:watch` | Run tests in watch mode (auto-rerun on changes) |
| `poe test:verbose` | Run tests with verbose output |
| `poe test:fast` | Run tests without coverage (fast, stops on first failure) |
| `poe test:failed` | Run only tests that failed in the last run |
| `poe test:specific <file>` | Run specific test file (e.g., `poe test:specific test_handler.py`) |

## Type Checking Tasks

| Command | Description |
|---------|-------------|
| `poe type` | Run mypy on source code only |
| `poe type:all` | Run mypy on source code and tests |
| `poe type:report` | Generate HTML coverage report for mypy |

## Linting & Formatting Tasks

| Command | Description |
|---------|-------------|
| `poe lint` | Check code with ruff (no changes) |
| `poe lint:fix` | Check and auto-fix issues with ruff |
| `poe format` | Format code with ruff |
| `poe format:check` | Check if code is formatted (no changes) |
| `poe fix` | Run lint with fixes + format (full cleanup) |

## Quality Check Tasks

| Command | Description |
|---------|-------------|
| `poe check` | Run type checking, linting, and format check |
| `poe check:all` | Run all checks plus tests with coverage |
| `poe ci` | Run full CI suite (same as GitHub Actions) |

## Documentation Tasks

| Command | Description |
|---------|-------------|
| `poe docs:serve` | Start MkDocs dev server with live reload at http://127.0.0.1:8000 |
| `poe docs:build` | Build documentation site to `site/` directory |
| `poe docs:deploy` | Deploy documentation to GitHub Pages |
| `poe docs:clean` | Remove built documentation |

## Development Tasks

| Command | Description |
|---------|-------------|
| `poe install` | Install package in editable mode with all dependencies |
| `poe clean` | Remove build artifacts, cache, and coverage reports |
| `poe clean:all` | Clean everything including virtual environment |

## Build & Release Tasks

| Command | Description |
|---------|-------------|
| `poe build` | Build distribution packages (wheel + sdist) |
| `poe build:check` | Build and validate distribution with twine |

## Quick Workflow Tasks

| Command | Description |
|---------|-------------|
| `poe dev` | Quick dev workflow: fix code and run tests |
| `poe pr` | Prepare for PR: fix code and run all checks |
| `poe all` | Run everything: fix, check, and test with coverage |

## Common Workflows

### Starting Development

```bash
# Clone and set up
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras

# Verify everything works
poe test
```

### During Development

```bash
# Quick iteration
poe dev                    # Fix + test (fast)

# Watch mode for TDD
poe test:watch            # Tests auto-run on file changes

# Before committing
poe pr                     # Full checks
```

### Working on Documentation

```bash
# Start live server
poe docs:serve            # Opens at http://127.0.0.1:8000

# Build to verify
poe docs:build

# Deploy to GitHub Pages
poe docs:deploy
```

### Before Creating a PR

```bash
# Run full suite
poe pr                     # or: poe check:all

# Verify CI will pass
poe ci
```

### Debugging Test Failures

```bash
# Run verbose
poe test:verbose

# Run only failed tests
poe test:failed

# Run specific test file
poe test:specific test_handler.py

# Run specific test
uv run pytest tests/test_handler.py::test_handler_call -v
```

## Configuration

All tasks are defined in [`tasks.toml`](tasks.toml). You can:

- View task definitions: `cat tasks.toml`
- Add custom tasks: Edit `tasks.toml`
- Chain tasks: Use `sequence` in task definitions

## Tips

1. **Use tab completion**: Poe supports shell completion
2. **Check help**: `poe <task> --help` for task-specific help
3. **Run in parallel**: Some tasks can run concurrently for speed
4. **CI equivalence**: `poe ci` runs exactly what GitHub Actions runs

## Troubleshooting

### Task not found

```bash
# List all tasks
poe

# Verify tasks.toml syntax
cat tasks.toml
```

### Dependencies missing

```bash
# Sync all dependencies
uv sync --all-extras

# Verify installation
poe install
```

### Tests failing

```bash
# Clean and reinstall
poe clean
uv sync --all-extras
poe test
```

## Integration with IDEs

### VS Code

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Test",
      "type": "shell",
      "command": "poe test",
      "group": "test"
    },
    {
      "label": "Test with Coverage",
      "type": "shell",
      "command": "poe test:cov",
      "group": "test"
    }
  ]
}
```

### PyCharm

1. Go to Settings → Tools → External Tools
2. Add new tool:
   - Name: `Poe Test`
   - Program: `uv`
   - Arguments: `run poe test`
   - Working directory: `$ProjectFileDir$`

## See Also

- [Contributing Guide](docs/development/contributing.md)
- [Development Setup](docs/development/setup.md)
- [Testing Guide](docs/development/testing.md)
