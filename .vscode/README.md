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

### 2. Install dependencies

`uv sync` alone only installs the default `dev` group (ruff, mypy, poethepoet). Test
dependencies live in a separate `test` dependency-group:

```bash
uv sync --all-extras --group test
```

### 3. Select Python Interpreter

1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "Python: Select Interpreter"
3. Choose the interpreter at `.venv/bin/python`

### 4. Running Tests

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

Use the `poe` tasks so local results match CI (see root `CLAUDE.md`):

```bash
# Run all tests
uv run poe test

# Run with coverage
uv run poe test:cov

# Run specific file
uv run poe test:specific test_handler.py
```

### 5. Debugging Tests

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

### 6. Type Checking

Type checking runs continuously via the mypy extension. You'll see:
- Red squiggly lines for errors
- Yellow squiggly lines for warnings

To manually run mypy (matches CI, uses `--strict`):
```bash
uv run poe type
```

Or use the task: "Type Check (mypy)"

### 7. Code Formatting

Code is automatically formatted on save using Ruff.

To manually format:
```bash
uv run poe format
```

Or use the task: "Format (ruff)"

### 8. Linting

Linting runs automatically on save.

To manually lint:
```bash
uv run poe lint
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

Type checking is provided by the `ms-python.mypy-type-checker` extension, which runs real
`mypy` in the background — separate from Pylance's own basic analysis
(`python.analysis.typeCheckingMode`). The mypy configuration lives in `mypy.ini` at the repo
root, not `pyproject.toml`.

`mypy-type-checker.ignorePatterns` excludes `tests/mypy/snippets/errors/**` from the extension's
diagnostics — those files are deliberately type-invalid (see `CLAUDE.md`). Pylance may still
flag them under its own basic analysis; that's a separate setting (`python.analysis.exclude`)
if you want to suppress those too.

### File Exclusions

The following are excluded from search and file watching to improve performance:
- `.venv/`
- `.mypy_cache/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `.coverage`
- `uv.lock` (committed, but large/generated — rarely useful in search)

## Troubleshooting

### Tests Not Discovered

1. Make sure you've selected the correct Python interpreter (`.venv/bin/python`)
2. Check the "Testing" panel for error messages
3. Try reloading VSCode: `Cmd+Shift+P` → "Developer: Reload Window"

### Mypy Import Errors

If you see "Cannot find implementation or library stub for module named 'pytest'":

1. Make sure you've synced with the `test` group: `uv sync --all-extras --group test`
2. Check `mypy.ini` at the repo root for the mypy configuration
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
