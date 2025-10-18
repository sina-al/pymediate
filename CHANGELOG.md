# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive GitHub Actions CI/CD workflows
  - Matrix testing across Python 3.10-3.13 and Ubuntu/macOS/Windows
  - Separate lint workflow with ruff and mypy
  - PR checks workflow with coverage diff, dependency review, and security scanning
  - Documentation workflow for markdown validation
  - Release workflow with automated changelog generation
- Optional dependency-injector integration via extras (`pip install pymediate[di]`)
- `DependencyInjectorResolver` for seamless DI container integration
- Comprehensive documentation:
  - ARCHITECTURE.md - detailed design philosophy and technical deep dive
  - CONTRIBUTING.md - contributor guidelines and development setup
  - Enhanced README.md with badges, installation options, and DI examples
- GitHub issue templates (bug report, feature request)
- Pull request template with comprehensive checklist
- pytest-github-actions-annotate-failures for better PR feedback
- Codecov integration for coverage tracking

### Changed
- Relaxed Python requirement from 3.13+ to 3.10+ for broader compatibility
- Moved dependency-injector from dev dependencies to optional extra
- Updated dependency version ranges for flexibility:
  - ruff: >=0.8.4
  - mypy: >=1.13.0
  - pytest: >=8.0.0
  - pytest-cov: >=4.1.0
  - dependency-injector: >=4.41.0

### Fixed
- Configuration separated into dedicated files (pytest.ini, mypy.ini, ruff.toml, .coveragerc)
- Improved VSCode integration with proper syntax highlighting for config files

## [0.1.0] - 2025-01-18

### Added
- Initial release of PyMediate
- Type-safe mediator pattern implementation
- Automatic response type inference via metaclasses
- Runtime validation of handler signatures
- `Request` base class with `RequestMeta` metaclass
- `Handler` generic base class with `HandlerMeta` metaclass
- `Resolver` protocol for dependency injection abstraction
- `SimpleResolver` implementation for basic use cases
- `Mediator` for request/response orchestration
- Comprehensive test suite with 55 tests and 95%+ coverage
- Support for dataclass-based requests and responses
- Type checking with mypy
- Code quality with ruff
- Development tooling with uv package manager

### Core Features
- Zero-boilerplate type safety: `Handler[MyRequest]` instead of `Handler[MyRequest, MyResponse]`
- Compile-time type checking with mypy
- Runtime type validation at class definition time
- Protocol-based resolver pattern for DI framework integration
- Clean separation of concerns across modules

[Unreleased]: https://github.com/sina-al/pymediate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sina-al/pymediate/releases/tag/v0.1.0
