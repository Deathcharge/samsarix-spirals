# Samsarix Spirals roadmap

This roadmap separates code completion, release, publication, and real adoption. Passing
one gate does not imply the next.

## Product position

Samsarix Spirals is a **hermetic JSON workflow contract runner** for developers, platform
teams, and AI-agent builders. It should make small data-shaping and policy flows easier to
review and safer to execute than an ad hoc script, while remaining dramatically smaller
than a general orchestrator.

The product earns its place only when all of these remain true:

- a workflow and its regression suite fit naturally beside application code;
- identical workflow and input JSON values produce identical results;
- execution needs no daemon, container runtime, credentials, network, subprocess, or
  dynamically loaded code;
- failure is bounded, attributable to a step, and useful in CI;
- the workflow is clearer to its owners than the equivalent bespoke script.

See [the competitive position](docs/COMPETITIVE_POSITIONING.md) for the evidence behind
this boundary.

## Flagship use cases

1. **Release manifest gates** — validate approval and required metadata, then emit a
   normalized manifest for a later publishing job.
2. **AI-output contracts** — turn untrusted structured model output into a bounded,
   regression-tested deterministic value before another system consumes it.
3. **Repository policy fixtures** — keep configuration and metadata expectations in
   reviewable JSON with positive and negative cases.
4. **Portable data-shaping checks** — produce the same small JSON artifact on a laptop,
   pre-commit hook, and CI runner without provider-specific syntax.

## Milestones

### 0.2 — Contract suites

- [x] Versioned suite files with named inputs.
- [x] Exact-output and expected-error assertions.
- [x] Human and machine-readable reports with CI exit behavior.
- [x] A realistic release-policy example.
- [x] Publish JSON Schemas for workflows and suites.
- [x] Emit JUnit XML for native CI test reporting.

### 0.3 — Useful deterministic shaping

- [x] Add bounded shallow object merge and explicit top-level key selection without
  arbitrary expressions.
- [ ] Add bounded list mapping, filtering, and string normalization without arbitrary
  expressions.
- [x] Add an `explain` command that shows dependencies and referenced input paths without
  executing the workflow.
- Define compatibility and deprecation rules for every schema-visible operation.
- [x] Prove an agent-output contract with adversarial extra-field, approval, and
  required-field fixtures.
- [ ] Prove a repository-policy example with adversarial fixtures.

### 0.4 — Repository adoption

- Ship a pinned GitHub Action and documented pre-commit integration.
- Add stable SARIF or annotation output for step-scoped failures.
- Publish signed distributions and an SBOM through an owned package-index account.
- Measure startup time, maximum-memory behavior, and fixture-suite throughput.

### 1.0 — Supported contract

- Freeze schema version 1 and its compatibility window.
- Publish a support policy and migration fixtures for schema version changes.
- Complete an independent security review of all parsing and amplification limits.
- Provide a rollback-tested release and incident process.

## Adoption gates

Do not describe Samsarix Spirals as production-ready until evidence shows:

- at least three independently owned repositories run it in CI;
- at least one flagship consumer has 30 consecutive days of successful contract checks;
- maintainers record 100 real workflow-suite executions with no nondeterministic result;
- at least one consumer demonstrates that a reviewed workflow is clearer or safer than
  its prior script using a written before/after evaluation;
- release artifacts, checksums, exact-head CI, support ownership, and rollback steps are
  recorded for the published version.

If those gates are not met, keep the project an honest alpha rather than expanding into
connectors, scheduling, hosted execution, or another general orchestration platform.
