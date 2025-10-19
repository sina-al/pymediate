# Changelog

All notable changes to PyMediate will be documented here.

## [Unreleased]

### Added
- Comprehensive test suite with 110+ tests
- Type inspection-based DI resolver (no naming conventions)
- Full dataclass support with Request[T] inheritance
- Type-safe SimpleResolver with runtime validation
- MkDocs Material documentation site
- Poe the Poet task automation
- Comprehensive error messages with documentation links

### Changed
- DI resolver now uses type inspection instead of naming conventions
- Updated to Python 3.12+ with PEP 695 type parameters
- Improved error messages

### Fixed
- Handler validation now checks exact parameter count
- Type safety enforcement at class definition time

## [0.1.0] - Initial Release

- Basic mediator pattern implementation
- Request/Handler/Mediator core
- SimpleResolver for basic use cases
- Type-safe handler registration
