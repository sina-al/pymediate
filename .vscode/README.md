# VS Code configuration for PyMediate

This directory contains VS Code–specific configuration for the PyMediate project.

## Files

- **settings.json** - Project-specific VS Code settings.
- **extensions.json** - Recommended extensions.
- **launch.json** - Debug configurations.
- **tasks.json** - Build and test tasks.

## Quick start

### 1. Install recommended extensions

When you open this project in VS Code, you'll be prompted to install recommended extensions. Select "Install All," or install them individually:

- **Python** - Python language support.
- **Pylance** - Fast Python language server.
- **Ruff** - Fast Python linter and formatter.
- **Mypy Type Checker** - Static type checking.
- **Python Test Adapter** - Test explorer integration.
- **Test Explorer UI** - Visual test runner.
- **Even Better TOML** - TOML syntax support for `pyproject.toml` and `tasks.toml`.
- **GitLens** - Inline blame and history.
- **Error Lens** - Inline error and warning highlighting.

### 2. Install dependencies

`uv sync` alone only installs the default `dev` group (ruff, mypy, poethepoet). Test
dependencies live in a separate `test` dependency-group:

```bash
uv sync --all-extras --group test
```

### 3. Select the Python interpreter

1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux).
2. Type "Python: Select Interpreter."
3. Choose the interpreter at `.venv/bin/python`.

### 4. Running tests

#### Option A: Using Test Explorer (recommended)

1. Select the Test beaker icon in the sidebar.
2. You'll see all your tests organized by file and class.
3. Select the play button next to any test to run it.
4. Select the debug icon to debug a test.

#### Option B: Using Command Palette

1. Press `Cmd+Shift+P` / `Ctrl+Shift+P`.
2. Type "Tasks: Run Task."
3. Choose one of:
      - "Run Tests" - Run all tests.
      - "Run Tests with Coverage" - Run with a coverage report.
      - "Run Current Test File" - Run tests in the current file.

#### Option C: Using keyboard shortcuts

- Run all tests: `Cmd+Shift+T` (configure in keyboard shortcuts).
- Run current file tests: Use the tasks menu.

#### Option D: Using the terminal

Use the `poe` tasks so local results match CI (see the root `CLAUDE.md`):

```bash
# Run all tests
uv run poe test

# Run with coverage
uv run poe test:cov

# Run a specific file
uv run poe test:specific test_handler.py
```

### 5. Debugging tests

1. Set breakpoints in your test or source code (select left of the line number).
2. Open the test file.
3. Press `F5`, or use the "Run and Debug" sidebar.
4. Choose "Python: Debug Tests."
5. Your test runs and stops at breakpoints.

**Pre-configured debug configurations:**

- **Python: Current File** - Debug the currently open Python file.
- **Python: Debug Tests** - Debug tests in the current file.
- **Python: Debug All Tests** - Debug all tests.
- **Python: Debug Specific Test** - Debug a specific test (prompts for a name).

### 6. Type checking

Type checking runs continuously via the mypy extension. You'll see:

- Red squiggly lines for errors.
- Yellow squiggly lines for warnings.

To manually run mypy (matches CI, uses `--strict`):

```bash
uv run poe type
```

Or use the task: "Type Check (mypy)."

### 7. Code formatting

Code is automatically formatted on save using Ruff.

To manually format:

```bash
uv run poe format
```

Or use the task: "Format (ruff)."

### 8. Linting

Linting runs automatically on save.

To manually lint:

```bash
uv run poe lint
```

Or use the task: "Lint (ruff)."

## Settings explained

### Python settings

```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"
```

Uses the project's virtual environment.

### Testing settings

```json
"python.testing.pytestEnabled": true
```

Enables pytest integration.

```json
"python.testing.autoTestDiscoverOnSaveEnabled": true
```

Automatically discovers new tests when you save files.

### mypy settings

Type checking is provided by the `ms-python.mypy-type-checker` extension, which runs real
`mypy` in the background — separate from Pylance's own basic analysis
(`python.analysis.typeCheckingMode`). The mypy configuration lives in `mypy.ini` at the repo
root, not `pyproject.toml`.

`mypy-type-checker.ignorePatterns` excludes `tests/typing/snippets/errors/**` from the extension's
diagnostics — those files are deliberately type-invalid (see `CLAUDE.md`). Pylance may still
flag them under its own basic analysis; that's a separate setting (`python.analysis.exclude`)
if you want to suppress those too.

### File exclusions

The following are excluded from search and file watching to improve performance:

- `.venv/`
- `.mypy_cache/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `.coverage`
- `uv.lock` (committed, but large and generated — rarely useful in search)

## Troubleshooting

### Tests not discovered

1. Make sure you've selected the correct Python interpreter (`.venv/bin/python`).
2. Check the "Testing" panel for error messages.
3. Try reloading VS Code: `Cmd+Shift+P` → "Developer: Reload Window."

### mypy import errors

If you see "Cannot find implementation or library stub for module named 'pytest'":

1. Make sure you've synced with the `test` group: `uv sync --all-extras --group test`.
2. Check `mypy.ini` at the repo root for the mypy configuration.
3. Reload VS Code.

### Auto-formatting not working

1. Check that the Ruff extension is installed.
2. Verify `charliermarsh.ruff` is enabled.
3. Check that `settings.json` has `"editor.formatOnSave": true`.

## Keyboard shortcuts

Add these to your VS Code keyboard shortcuts (`Cmd+K Cmd+S`):

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

## Additional resources

- [VS Code Python testing](https://code.visualstudio.com/docs/python/testing)
- [VS Code Python debugging](https://code.visualstudio.com/docs/python/debugging)
- [pytest documentation](https://docs.pytest.org/)
- [mypy documentation](https://mypy.readthedocs.io/)
