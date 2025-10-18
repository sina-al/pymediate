# VSCode Configuration for PyMediate

This directory contains VSCode-specific configuration for the PyMediate project.

## Files

- **settings.json** - Project-specific VSCode settings
- **extensions.json** - Recommended extensions
- **launch.json** - Debug configurations
- **tasks.json** - Build and test tasks

## Quick Start

### 1. Install Recommended Extensions

When you open this project in VSCode, you'll be prompted to install recommended extensions. Click "Install All" or install them individually:

- **Python** - Python language support
- **Pylance** - Fast Python language server
- **Ruff** - Fast Python linter and formatter
- **Mypy Type Checker** - Static type checking
- **Python Test Adapter** - Test explorer integration
- **Test Explorer UI** - Visual test runner

### 2. Select Python Interpreter

1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "Python: Select Interpreter"
3. Choose the interpreter at `.venv/bin/python`

### 3. Running Tests

#### Option A: Using Test Explorer (Recommended)

1. Click the Test beaker icon in the sidebar
2. You'll see all your tests organized by file and class
3. Click the play button next to any test to run it
4. Click the debug icon to debug a test

#### Option B: Using Command Palette

1. Press `Cmd+Shift+P` / `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. Choose one of:
   - "Run Tests" - Run all tests
   - "Run Tests with Coverage" - Run with coverage report
   - "Run Current Test File" - Run tests in current file

#### Option C: Using Keyboard Shortcuts

- Run all tests: `Cmd+Shift+T` (configure in keyboard shortcuts)
- Run current file tests: Use tasks menu

#### Option D: Using Terminal

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=pymediate --cov-report=term-missing

# Run specific file
uv run pytest tests/test_handler.py -v

# Run specific test
uv run pytest tests/test_handler.py::TestHandler::test_handler_call -v
```

### 4. Debugging Tests

1. Set breakpoints in your test or source code (click left of line number)
2. Open the test file
3. Press `F5` or use the "Run and Debug" sidebar
4. Choose "Python: Debug Tests"
5. Your test will run and stop at breakpoints

**Pre-configured debug configurations:**
- **Python: Current File** - Debug the currently open Python file
- **Python: Debug Tests** - Debug tests in the current file
- **Python: Debug All Tests** - Debug all tests
- **Python: Debug Specific Test** - Debug a specific test (will prompt for name)

### 5. Type Checking

Type checking runs automatically on save. You'll see:
- Red squiggly lines for errors
- Yellow squiggly lines for warnings

To manually run mypy:
```bash
uv run mypy src/pymediate/
```

Or use the task: "Type Check (mypy)"

### 6. Code Formatting

Code is automatically formatted on save using Ruff.

To manually format:
```bash
uv run ruff format src/ tests/
```

Or use the task: "Format (ruff)"

### 7. Linting

Linting runs automatically on save.

To manually lint:
```bash
uv run ruff check src/ tests/
```

Or use the task: "Lint (ruff)"

## Settings Explained

### Python Settings

```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"
```
Uses the project's virtual environment.

### Testing Settings

```json
"python.testing.pytestEnabled": true
```
Enables pytest integration.

```json
"python.testing.autoTestDiscoverOnSaveEnabled": true
```
Automatically discovers new tests when you save files.

### Mypy Settings

```json
"python.linting.mypyEnabled": true
```
Enables mypy type checking.

The mypy configuration is in `pyproject.toml` under `[tool.mypy]`.

### File Exclusions

The following are excluded from search and file watching to improve performance:
- `.venv/`
- `.mypy_cache/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `.coverage`
- `uv.lock`

## Troubleshooting

### Tests Not Discovered

1. Make sure you've selected the correct Python interpreter (`.venv/bin/python`)
2. Check the "Testing" panel for error messages
3. Try reloading VSCode: `Cmd+Shift+P` → "Developer: Reload Window"

### Mypy Import Errors

If you see "Cannot find implementation or library stub for module named 'pytest'":

1. Make sure mypy is installed in your venv: `uv add --dev mypy`
2. Check that `pyproject.toml` has the mypy configuration
3. Reload VSCode

### Auto-formatting Not Working

1. Check that Ruff extension is installed
2. Verify `charliermarsh.ruff` is enabled
3. Check `settings.json` has `"editor.formatOnSave": true`

## Keyboard Shortcuts

Add these to your VSCode keyboard shortcuts (`Cmd+K Cmd+S`):

```json
[
  {
    "key": "cmd+shift+t",
    "command": "workbench.action.tasks.runTask",
    "args": "Run Tests"
  },
  {
    "key": "cmd+shift+c",
    "command": "workbench.action.tasks.runTask",
    "args": "Run Tests with Coverage"
  }
]
```

## Additional Resources

- [VSCode Python Testing](https://code.visualstudio.com/docs/python/testing)
- [VSCode Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [pytest Documentation](https://docs.pytest.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
