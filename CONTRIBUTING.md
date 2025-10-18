# Contributing to PyMediate

Thank you for your interest in contributing to PyMediate! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

### Our Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- Git
- A GitHub account

### Finding Issues to Work On

- Check the [issue tracker](https://github.com/your-org/pymediate/issues)
- Look for issues labeled `good first issue` or `help wanted`
- Feel free to ask questions in issue comments before starting work
- If you have an idea for a new feature, open an issue to discuss it first

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/pymediate.git
cd pymediate

# Add the upstream repository
git remote add upstream https://github.com/your-org/pymediate.git
```

### 2. Install Dependencies

#### Using uv (Recommended)

```bash
# Install all dependencies including dev and optional extras
uv sync --all-extras

# Or install specific groups
uv sync              # Core dependencies only
uv sync --group dev  # Dev dependencies
```

#### Using pip

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with all extras
pip install -e ".[dev,di]"
```

### 3. Verify Installation

```bash
# Run tests to verify everything works
uv run pytest

# Run type checking
uv run mypy src/pymediate/

# Run linting
uv run ruff check src/ tests/
```

### 4. Set Up Pre-commit Hooks (Optional)

```bash
# Install pre-commit
uv pip install pre-commit

# Install the git hooks
pre-commit install
```

## Development Workflow

### 1. Create a Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a new branch for your work
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions or changes

### 2. Make Your Changes

Follow the [Coding Standards](#coding-standards) section below.

### 3. Run Tests and Checks

```bash
# Run all tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=pymediate --cov-report=term-missing

# Run type checking
uv run mypy src/pymediate/ tests/

# Run linting
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

### 4. Commit Your Changes

We follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:

```bash
git add .
git commit -m "feat: add async handler support"
# or
git commit -m "fix(handler): correct type validation for optional fields"
```

Commit message format:
```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions or changes
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

### 5. Push and Create Pull Request

```bash
# Push your branch
git push origin feature/your-feature-name

# Create a pull request on GitHub
```

## Coding Standards

### Python Style

We use Python 3.10+ features and follow modern Python best practices.

#### Type Hints

**All public APIs must have complete type hints:**

```python
# Good
def send(self, request: RequestType) -> ResponseType:
    """Send a request and return its response."""
    ...

# Bad - missing type hints
def send(self, request):
    ...
```

#### Docstrings

**All public classes, methods, and functions need docstrings:**

```python
def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
    """Resolve a request class to its handler.

    Args:
        request_class: The request class to resolve

    Returns:
        Handler instance for the request

    Raises:
        ValueError: If no handler is registered for the request class
    """
    ...
```

We follow [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

#### Code Organization

- **Modules**: Each module should have a single, well-defined responsibility
- **Classes**: Keep classes focused and cohesive
- **Functions**: Functions should do one thing well
- **Imports**: Group imports in this order:
  1. Standard library
  2. Third-party packages
  3. Local modules

```python
# Good
import inspect
from typing import Any, Protocol

from dependency_injector import containers

from pymediate.handler import Handler
```

#### Naming Conventions

- **Classes**: `PascalCase` (e.g., `RequestHandler`, `SimpleResolver`)
- **Functions/Methods**: `snake_case` (e.g., `send_request`, `validate_handler`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `_REQUEST_REGISTRY`, `MAX_RETRIES`)
- **Private members**: Prefix with `_` (e.g., `_resolver`, `_validate_call_signature`)

### Code Quality

#### Ruff Configuration

We use Ruff for linting and formatting. Configuration is in [ruff.toml](ruff.toml).

```bash
# Check for issues
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check src/ tests/ --fix

# Format code
uv run ruff format src/ tests/
```

#### Mypy Configuration

We use mypy for static type checking. Configuration is in [mypy.ini](mypy.ini).

```bash
# Run type checking
uv run mypy src/pymediate/ tests/
```

### Architecture Guidelines

When adding new features or modifying existing code:

1. **Read [ARCHITECTURE.md](ARCHITECTURE.md)** to understand the design philosophy
2. **Maintain separation of concerns**: Each module has a specific role
3. **Preserve type safety**: Both runtime and static type checking should work
4. **Keep the core simple**: Advanced features should be opt-in
5. **Protocol over inheritance**: Use protocols for interfaces when possible

#### Key Design Principles

1. **Type Inference Over Explicit Declaration**
   - Don't make users repeat type information
   - Use metaclasses to extract and validate types automatically

2. **Fail Fast with Clear Messages**
   - Catch errors at class definition time, not runtime
   - Provide actionable error messages with context

3. **Protocol-Based Extensibility**
   - Use `Protocol` for interfaces, not ABC
   - Enable duck typing with type safety

4. **Optional Dependencies**
   - Core functionality must have zero dependencies
   - Advanced features (like DI) are opt-in via extras

## Testing

### Test Organization

Tests are organized by module:

```
tests/
├── test_request.py           # Request and RequestMeta tests
├── test_handler.py           # Handler and HandlerMeta tests
├── test_resolver.py          # Resolver protocol and SimpleResolver
├── test_mediator.py          # Mediator tests
├── test_integration.py       # End-to-end integration tests
├── test_dataclass_support.py # Dataclass usage patterns
└── test_di_resolver.py       # DI integration tests
```

### Writing Tests

We use **function-based tests** (pytest style), not class-based tests:

```python
# Good - function-based
def test_handler_validates_return_type():
    """Test that handler validates return type at class definition."""
    class TestResponse:
        def __init__(self, value: int):
            self.value = value

    class TestRequest(Request, response_type=TestResponse):
        pass

    # This should raise TypeError
    with pytest.raises(TypeError, match="must return TestResponse"):
        class BadHandler(Handler[TestRequest]):
            def __call__(self, request: TestRequest) -> str:  # Wrong type!
                return "hello"

# Bad - class-based (avoid)
class TestHandler:
    def test_validation(self):
        ...
```

### Test Coverage

- **Minimum coverage: 95%** for all code
- **Aim for 100%** coverage on core modules (`handler.py`, `mediator.py`, `request.py`, `resolver.py`)
- Coverage configuration is in [.coveragerc](.coveragerc)

```bash
# Run with coverage report
uv run pytest --cov=pymediate --cov-report=term-missing

# Fail if coverage is below threshold
uv run pytest --cov=pymediate --cov-fail-under=95
```

### Test Categories

1. **Unit Tests**: Test individual functions/classes in isolation
2. **Integration Tests**: Test components working together
3. **Type Tests**: Verify that type errors are caught
4. **Dataclass Tests**: Real-world usage patterns with dataclasses

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_handler.py

# Run specific test function
uv run pytest tests/test_handler.py::test_handler_validates_return_type

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=pymediate --cov-report=term-missing

# Run tests matching a pattern
uv run pytest -k "dataclass"
```

### Testing Matrix

We test against:
- **Python versions**: 3.10, 3.11, 3.12, 3.13
- **Operating systems**: Ubuntu, macOS, Windows
- **With and without optional dependencies**

This is automated in our CI/CD pipeline.

## Documentation

### Updating Documentation

When making changes, update relevant documentation:

1. **Docstrings**: Update function/class docstrings
2. **README.md**: Update if public API changes
3. **ARCHITECTURE.md**: Update if architecture changes
4. **CONTRIBUTING.md**: Update if development process changes
5. **Examples**: Add examples for new features

### Documentation Standards

- Use clear, concise language
- Include code examples for features
- Keep examples up-to-date and tested
- Use proper markdown formatting

### Code Examples

Code examples in documentation should:
- Be complete and runnable
- Follow our coding standards
- Use type hints
- Include imports

```python
# Good example in documentation
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

@dataclass
class UserResponse:
    user_id: int
    username: str

class GetUserRequest(Request, response_type=UserResponse):
    def __init__(self, user_id: int):
        self.user_id = user_id

class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=request.user_id, username="alice")

# Setup and usage
resolver = SimpleResolver()
resolver.register(GetUserRequest, GetUserHandler())
mediator = Mediator(resolver)

response = mediator.send(GetUserRequest(user_id=1))
print(response.username)  # "alice"
```

## Pull Request Process

### Before Submitting

Ensure your PR:
- ✅ Passes all tests (`uv run pytest`)
- ✅ Passes type checking (`uv run mypy src/pymediate/ tests/`)
- ✅ Passes linting (`uv run ruff check src/ tests/`)
- ✅ Is formatted (`uv run ruff format src/ tests/`)
- ✅ Has test coverage ≥95%
- ✅ Has appropriate documentation
- ✅ Follows conventional commit format

### PR Title Format

Use conventional commit format:

```
feat: add async handler support
fix(handler): correct type validation for optional fields
docs: update README with DI examples
test: add comprehensive dataclass tests
```

### PR Description Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Changes Made
- List specific changes
- Include any design decisions

## Testing
- Describe testing done
- Include test coverage information

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally
- [ ] Coverage is ≥95%
```

### Review Process

1. **Automated Checks**: CI/CD will run tests, linting, type checking
2. **Code Review**: Maintainer will review code and provide feedback
3. **Iteration**: Address feedback and push updates
4. **Approval**: Once approved, maintainer will merge

### After Your PR is Merged

- Delete your branch
- Update your fork's main branch
- Celebrate! 🎉

```bash
# Update your main branch
git checkout main
git pull upstream main
git push origin main

# Delete the feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

## Release Process

Releases are handled by maintainers. The process:

1. **Version Bump**: Update version in `pyproject.toml` and `src/pymediate/__init__.py`
2. **Changelog**: Update `CHANGELOG.md`
3. **Tag**: Create git tag (`git tag v0.2.0`)
4. **Push**: Push tag to trigger release workflow
5. **GitHub Release**: Automatically created by CI/CD
6. **PyPI**: (When ready) Automatically published by CI/CD

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes (backward compatible)

## Getting Help

- **Questions**: Open a [discussion](https://github.com/your-org/pymediate/discussions)
- **Bugs**: Open an [issue](https://github.com/your-org/pymediate/issues)
- **Security**: Email security@example.com (do not open public issues)

## Recognition

Contributors will be:
- Listed in `CONTRIBUTORS.md`
- Mentioned in release notes
- Credited in the git history

Thank you for contributing to PyMediate! 🚀
