# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions
use semantic versioning while the public API remains pre-1.0.

## [Unreleased]

### Changed

- Renamed the product, distribution, import package, CLI, and public base exception from
  Helix Spirals to Samsarix Spirals under Samsarix LLC ownership.
- Replaced the inconsistent custom BSL text with the unmodified Mozilla Public License 2.0
  and added SPDX, copyright, contact, and notice metadata.

## [0.1.0] - 2026-07-28

### Added

- A bounded JSON workflow format with `set` and `assert` operations.
- Deterministic template rendering from input, defaults, and prior step outputs.
- `validate`, `run`, and non-overwriting `init` CLI commands.
- A small typed Python API, examples, tests, CI, security guidance, and release checks.

### Removed

- The non-standalone FastAPI, PostgreSQL, Redis, OAuth, marketplace, agent, scheduler,
  webhook, and third-party connector prototypes.
- Unverified integration counts, benchmarks, compliance claims, and incompatible API
  documentation.
