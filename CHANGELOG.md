# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions
use semantic versioning while the public API remains pre-1.0.

## [Unreleased]

### Added

- `run --output-only` for piping the raw final JSON value without intermediate trace
  entries; the default trace format remains compatible.

### Fixed

- Template expansion now accounts for the surrounding tree's depth when cloning an
  input or prior-step value. Individually valid trees can no longer compose into results
  exceeding the documented nesting limit, including explicit final output templates.
- Assertions now use the same JSON equality as suite expectations, including array
  membership and nested values. `1`/`0` no longer satisfy `true`/`false` approval gates;
  numeric `1` and `1.0` still compare equal. Workflows relying on Python's former
  boolean/number equivalence must provide correctly typed inputs.
- Agent policy metadata is applied after untrusted result data, so it cannot be replaced
  by agent-supplied `source` or `reviewed` values.
- Repository-policy fixtures now require literal boolean states and explicitly private
  visibility, rejecting truthy strings, null archive state, and unknown visibility.

### Previously added

- Versioned, bounded workflow regression suites with exact-output and expected-error
  contracts through the Python API and `samsarix-spirals test` command.
- A release-policy example that demonstrates a practical CI approval gate.
- Competitive positioning, flagship use cases, and measurable adoption gates.
- Bundled JSON Schema Draft 2020-12 documents with CLI and Python discovery APIs.
- Deterministic, value-redacted JUnit XML reports for native CI ingestion.
- Bounded `merge` and `pick` operations for shallow object composition and explicit
  top-level output allowlists.
- An agent tool-result example with approval, required-field, and adversarial extra-field
  regression cases.
- A value-free `explain` API and CLI command for input/default path inventory and direct
  step-dependency review without workflow execution.
- A documented compatibility/deprecation policy and adversarial production-repository
  policy contract.
- Automatic execution coverage for every checked-in example suite.

### Changed

- Exact suite-output comparison now distinguishes JSON booleans from numbers while
  retaining JSON numeric equality between integer and decimal representations.

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
