# Changelog

All notable changes are recorded here. The format follows Keep a Changelog; versions
use semantic versioning while the public API remains pre-1.0.

## [Unreleased]

### Added

- Suite JSON failure codes and actual failing step IDs, with step context in human CLI,
  JUnit and GitHub diagnostics. Passing-case shape, generic detail strings, suite
  expectations and exit codes remain compatible. Runtime messages and fixture values
  remain excluded; final/run-level errors are not assigned a fabricated step.
- A dependency-free maintainer benchmark harness for CLI startup, fixture throughput,
  retained traces, report serialization and byte-budget rejection. Fresh-process OS
  memory counters and separate Python allocation measurements include raw samples and
  source fingerprints; cross-platform CI checks outcomes without speed thresholds.
- Resource-measurement documentation distinguishes encoded payload caps from RAM usage,
  representative stress probes from worst-case proofs, and synthetic runs from adoption.
- A SHA-pinned composite GitHub Action and Python pre-commit hook for workflow suites,
  plus the `samsarix-spirals-ci` single-line reporting command. The Action uses isolated
  pinned source, workspace-contained inputs, and escaped/bounded failure annotations.
- Fresh-consumer integration tests and Linux/Windows/macOS hosted verification; complete
  setup instructions distinguish source pinning from locked/offline environment builds.
- Bounded `map`/`filter` list operations with scoped `item` templates, shared output/work
  budgets, fail-fast indexed errors, and JSON comparison semantics. `normalize` applies
  ordered ASCII trim/lower/upper transforms to strings or string arrays. These are
  additive schema-version-1 operations; existing workflows retain their behavior.
- Bundled structural schemas and `explain` item-reference inventories for the new
  operations, plus a runnable release-target batch example and eight regression cases.
- `run --output-only` for piping the raw final JSON value without intermediate trace
  entries; the default trace format remains compatible.

### Fixed

- Resource-exhaustion hardening: rendered arguments/final values now have a 4 MiB
  encoded-payload cap, and retained step outputs plus final output have a combined
  16 MiB cap. Accounting includes JSON escaping and repeated copies. Previously valid
  amplification-heavy workflows may now fail with an execution error; reduce payloads
  or split batches. See the workflow format for the exact accounting contract.
- API factories normalize accepted nested tuples and mappings into JSON arrays/objects,
  closing an alternate representation that bypassed renderer traversal. Suite expectations
  use the same normalization. Integers that cannot be rendered under Python's conversion
  limit fail with an attributed execution error rather than a raw encoder exception.
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

- Removed redundant private trace and operation-argument copies while preserving detached
  public step/final/report outputs and all resource budgets. Added all-operation mutation
  regressions and before/after measurements; trace-only allocation improved in the recorded
  workload, while full-report memory remained essentially unchanged.
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
