# Productization record

Last updated: 2026-08-31

## Current disposition

Samsarix Spirals is now a **local 0.1.0 source release candidate** for a deterministic,
side-effect-free JSON workflow runner. Its supported journey is:

1. install the package on Python 3.11 or newer;
2. validate and statically explain a checked-in workflow;
3. run regression suites with expected success and failure cases;
4. run it with a JSON input object;
5. consume final JSON via `--output-only`, or inspect the full diagnostic trace locally.

Local quality gates and a clean-wheel smoke test are release requirements. A public
release is not claimed until the exact commit passes the hosted CI matrix, the package
name and publisher account are confirmed, and an authorized maintainer creates the tag
and publishes the artifacts.

The starting-state audit and original verification below are historical evidence, not
the current feature inventory. The latest revalidation is recorded in the next section.

## 2026-08-31 revalidation and contract-boundary corrections

The starting revision for this pass was `d3b7b28`, with a clean worktree and no open PRs.
The intervening merged work added regression suites, JSON Schemas, JUnit reports, object
shaping, static explanations, realistic policy examples, and compatibility guidance.
The GitHub repository already uses `Deathcharge/samsarix-spirals`; no slug rename remains.

Baseline: `python -m pytest -q` passed 114 tests, skipped two input-file schema checks,
and measured 96.79% branch-aware coverage on Python 3.14.7. Passing that suite did not
prove the advertised data boundaries: direct public-API reproductions showed all three
of the following, subsequently captured in failing regression tests:

| Priority | Observed gap | Correction |
| --- | --- | --- |
| P1 | Numeric `1` satisfied literal boolean approval in `assert`, while suites treated the types differently. | Share recursive JSON equality across assertions, array membership, and suite expectations. |
| P1 | An earlier merge output retained credential-shaped fields in CLI stdout after a final allowlist removed them. | Add `run --output-only` and document final values versus diagnostic traces; preserve the existing trace interface. |
| P1 | Agent result data overwrote trusted policy metadata; repository gates accepted truthy strings and unknown visibility. | Apply trusted metadata last and use explicit boolean/private-state gates, with portable negative fixtures. |
| P1 | The living record and security boundary still described only the initial two-operation core. | Refresh the supported surface, evidence, disclosure caveats, and release blockers. |

The new boundary test module initially produced 27 failures and 15 passes, demonstrating
that it catches the defects and missing CLI mode before implementation. The complete
suite after corrections passes 156 tests at 96.96% coverage (additional input schema
fixtures are intentionally skipped). Exact final package and hosted-CI evidence is
recorded in the pull request for this pass; do not infer publication from a green PR.

Bounded primary-source research was refreshed on 2026-08-31:

- [JSON Schema boolean semantics](https://json-schema.org/understanding-json-schema/reference/boolean)
  distinguish booleans from numeric truthy values, supporting the corrected JSON contract.
- [CUE's validation command](https://cuelang.org/docs/reference/command/cue-help-vet/)
  already validates several configuration formats and checks concreteness. Inference:
  Spirals should earn adoption through its small, suite-tested JSON transformation path,
  not claim broader validation capabilities than a mature constraint language.

Next by value: finish bounded shaping after contract correctness, add pinned repository
integration, measure real resource use, prepare reproducible publisher-owned artifacts,
and validate the workflow in independently owned repositories. No production-readiness,
external adoption, private reporting enablement, or package publication is asserted.

### Follow-up: composed render depth

A separate bounded reproduction combined depth-12 input and template trees into an
accepted depth-24 result, contradicting the documented limit of 20. The renderer now
carries the surrounding depth into placeholder cloning and recursive literal rendering.
Five regression cases failed before the fix; after it, object/array expansion, explicit
final output, and prior-step growth are rejected at the boundary, while exact-depth-20
results still succeed. A further case verifies merged objects cannot exceed the combined
10,000-key limit; this removes an incorrect claim that the value budget made that path
unreachable. Local pytest after this follow-up: 164 passed, 3 intentional schema skips,
96.83% coverage on Python 3.14.7.

### Follow-up: bounded list shaping

The prior checkout could project a single object but could not express a batch
transformation: `map` was rejected as an unknown operation and `item` as an unknown
template root. The new release-target journey filters enabled records, projects their
names, and normalizes ASCII labels before handing JSON to a later CI job. It is a
runnable reference use case, not evidence of independent adoption or authorization.

Added `map`, `filter`, and `normalize` with version-1 structural schemas. Local `item`
references are limited to map templates/filter predicates and appear separately in
static explanations. All list output/predicate work shares the established budgets;
there is no per-item reset, nested workflow, arbitrary expression, regex, or I/O.
Filtering uses existing strict JSON comparisons and errors on missing/malformed values.
Normalization is intentionally ASCII-only, ordered, non-expanding, and not sanitization.

The [jq manual](https://jqlang.org/manual/dev/) documents much broader mapping/filtering
capabilities. Inference: copying that expression language is not a differentiation
strategy. This addition instead completes a small reviewable batch contract with schema,
positive/negative fixtures, attributable errors, and static reference inventory. The
downstream caller still owns allowlists, authorization, duplicates, and safe command use.

Initial new-operation tests: 52 passed alongside all 199 previous tests (97.32% overall
coverage on Python 3.14.7). Final local regression coverage includes 259 passing tests,
four intentional input-schema skips, and 97.33% coverage. The fresh installed wheel
passes all four example suites, the batch CLI output/explanation checks, and previous
approval/byte-limit checks. Exact-head hosted-CI evidence is recorded in the milestone
PR. Repository integrations, measured workloads, owned release
artifacts, and independent adoption remain the next gates; no production claim is added.

### Follow-up: aggregate encoded payload budgets

A bounded reproduction used a 1,111-byte workflow and 100,012-byte input to produce
a 5,000,161-byte step payload and 10,000,456-byte full compact result. Each string was
within the existing character limit; repeated placeholders bypassed any practical
aggregate size control. Accepted API tuples also bypassed list traversal. The initial
24 regression cases failed before the fix (after shortening oversized pytest case IDs).

The shared renderer now incrementally enforces a 4 MiB compact ASCII-escaped JSON
budget for arguments/final values. The runner counts retained step outputs and final
output against 16 MiB before returning a result, including the implicit final copy.
Validated API mappings/tuples normalize consistently across workflow, input, and suite
factories. Oversized integer conversion failures retain execution-error semantics.
This is an intentional resource-exhaustion tightening under the compatibility policy;
oversized users must reduce payloads or split batches, not disable accounting.

Tests cover all operations, all CLI output modes, literal/exact/interpolated text,
Unicode and escaped keys, scalar/punctuation boundaries, per-run resets, tuple-backed
suite expectations, and explicit/implicit final values. Local full pytest: 199 passed,
3 intentional schema skips, 97.03% coverage on Python 3.14.7. Fresh-wheel smoke checks
also exercise per-render and cumulative failures with empty stdout. Exact final artifact
and hosted CI outcomes are recorded in the milestone PR.

The accounting choice follows [Python's JSON encoder contract](https://docs.python.org/3/library/json.html):
ASCII escaping gives a deterministic encoding measure, while fragment iteration avoids
allocating a second full encoded result just to measure it. No runtime dependency added.

Remaining resource work is explicit: encoded payload budgets are not measured process
memory, wall-clock deadlines, or exact pretty-printed stdout limits. Metadata, temporary
copies, interpreter overhead, and caller-owned/mutated API objects are outside the
payload measure. Hostile multi-tenant hosting remains unsupported; retain independent
security review and measured workload/resource validation as release gates.

Sustainability hypothesis (not validated demand): keep the MPL-covered local runner
usable without an account; offer optional workflow migration, integration assistance,
and support through Samsarix LLC. The core has no metered API or hosting cost, but uses
the caller's CPU/memory and CI minutes. Do not add telemetry or a hosted subscription
without a demonstrated customer need and an explicit operating boundary.

## Starting-state audit

The starting revision was `3d67b511a5c29b3a3def1f0ad0b17cc4d80a69d0` on `master`,
tracking `origin/master`, with no user changes, additional worktrees, submodules, tags,
or releases. Git history consisted of an initial 37,113-line import followed by generated-
looking integration, documentation, and test additions. It did not show an earlier small,
working product to preserve.

Baseline commands produced these results before implementation:

| Check | Baseline result |
| --- | --- |
| `python --version` | Python 3.11.9. |
| `python -m compileall -q src tests examples` | Failed: five test files used the invalid decorator syntax `pytest.mark.async`. |
| `python -m pytest` | Failed during `tests/conftest.py` parsing; no tests ran. |
| `python -m black --check src tests examples` | Failed; 64 files needed formatting and five tests could not be parsed. |
| `python -m isort --check-only src tests examples` | Failed because `multi_line_mode` was not a supported setting. |
| `python -m flake8 src tests examples` | Failed with more than 2,700 reported lines, including syntax errors. |
| `python -m mypy src` | Failed across most modules, including Python-version conflicts, missing private imports, and incompatible integration bases. |
| `python -m build` | Built archives, but included the broken server and connector code; artifact creation did not prove importability or usability. |
| Installed/import smoke test | Failed before productization: the src-layout package was not installed and the documented public classes did not exist. |

The repository claimed Apache 2.0, MIT, proprietary dual licensing, and Business Source
License terms in different files. It claimed 130+ integrations, production benchmarks,
AES-256 credential storage, RBAC, SOC 2 readiness, Docker support, and production-green
tests without matching evidence. The console entry referenced a missing `main()` function,
and the documented `WorkflowEngine`, `WorkflowNode`, and `IntegrationNode` API did not
exist as described.

### Security findings in the removed server prototype

The audit traced several concrete issues through mounted or intended product paths:

- `GET /spirals` passed `user_id=None` for an unauthenticated request, causing storage
  to query every workflow and reconstruct decrypted action configuration.
- `POST /spirals/{id}/clone` loaded and copied a source workflow without an ownership
  check, allowing protected configuration to cross a user boundary when an ID was known.
- credential encryption caught initialization and encryption failures and returned the
  original plaintext, while storage continued saving the action configuration.
- a generic webhook action accepted attacker-controlled destinations without a complete
  internal-address or redirect control, creating an SSRF-capable sink in the intended
  execution path.
- the health handler acquired a PostgreSQL connection without releasing it, and several
  public real-time or trigger paths had no bounded authentication/resource design.

Dynamic HTTP reproduction was blocked because the application could not import without
private `apps.backend` modules and also required unconfigured PostgreSQL and Redis
services. Static confidence was still high for the authorization and encryption paths:
the source, missing control, storage sink, route mounting, and sensitive-data impact were
visible in the repository. The correct product fix was removal of that unsupported server
surface, not a narrow patch that left its untestable architecture in release artifacts.

## Complete file disposition

All tracked starting files were inventoried. The disposition was:

- **Root metadata:** `.gitignore`, `CONTRIBUTING.md`, `LICENSE`, `README.md`, and
  `pyproject.toml` were rewritten or corrected. `setup.py` was removed to eliminate
  duplicate package metadata; `MANIFEST.in` was replaced with an explicit sdist-only
  documentation/example list. `LICENSE.PROPRIETARY` was removed
  because it implied an undocumented second license and used a conflicting contact domain.
- **Aspirational root documents:** `ARCHITECTURE.md`, `IMPROVEMENTS_SUMMARY.md`, and
  `README_UPDATED.md` were removed because they described unsupported systems or
  contradicted the actual license.
- **Old docs:** `docs/API.md`, `API_REFERENCE.md`, `ARCHITECTURE.md`,
  `ERROR_HANDLING.md`, `INTEGRATIONS_GUIDE.md`, `QUICKSTART.md`, and `TESTING.md` were
  removed. They documented nonexistent APIs, invalid commands, or unverified capabilities.
- **Old examples:** the three Python examples and their README were removed because they
  imported nonexistent classes and demonstrated network integrations that were not safe
  or runnable. They were replaced by executable JSON examples.
- **Server/runtime prototype:** `actions.py`, `additional_integrations.py`,
  `advanced_nodes.py`, `api_routes.py`, `context_as_service.py`, `copilot.py`,
  `credential_encryption.py`, `engine.py`, `error_handling.py`, `event_bus.py`, both
  generic HTTP connector modules, `integration_nodes.py`, `integration_routes.py`,
  `main.py`, `meta_learning_engine.py`, `models.py`, `oauth_callbacks.py`, `optimizer.py`,
  `routes.py`, `scheduler.py`, `storage.py`, `test_ucf_integration.py`, `webhooks.py`,
  `workflow_templates.py`, and `zapier_import.py` were removed. They were coupled to a
  private monorepo, external services, contradictory models, and unsafe/unverified paths.
- **Integration package:** all Airtable, Asana, AWS, Calendly, Datadog, Discord, GitHub,
  Google Cloud/Drive, HubSpot, Intercom, Jira, Linear, Mailchimp, Mixpanel, Monday, Notion,
  PayPal, Segment, SendGrid, Sentry, Slack, Stripe, Twilio, Zapier, and base/registry files
  were removed. Many imported a nonexistent `BaseIntegration`; none had credible live
  contract tests. The project does not claim integrations in 0.1.
- **Marketplace, OAuth, and versioning packages:** removed in full. They either imported
  private services or required a persistent multi-user product boundary that this release
  does not implement.
- **Old tests:** all seven starting test files were removed. Five did not parse, and the
  remaining files mostly tested local fixture builders rather than shipped behavior. Four
  focused test modules now cover the public model, runner, CLI, and exports.

No original runtime module is silently retained as a supported legacy path. Git history
remains the recovery mechanism for prototype research; release artifacts contain only the
new standalone package.

## Market and ecosystem check

Research was bounded to official product and packaging documentation current on
2026-07-28:

- [n8n](https://docs.n8n.io/) is a broad fair-code automation platform with a UI,
  hosting modes, integrations, credentials, and a much larger security/operations surface.
- [Temporal](https://docs.temporal.io/) targets durable, crash-recovering distributed
  application execution.
- [Prefect](https://docs.prefect.io/v3/concepts/flows) turns Python functions into
  observed, retryable flows and supports deployments and scheduling.
- [Dagster](https://docs.dagster.io/) targets data orchestration with assets, lineage,
  observability, and a declarative Python model.
- The [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  recommends validating the installed copy with a src layout, while its
  [CLI guide](https://packaging.python.org/en/latest/guides/creating-command-line-tools/)
  documents console entry points and `__main__.py`.

Inference from that comparison: another hosted connector platform or Python orchestrator
would be undifferentiated and far beyond this repository's verified capacity. The credible
niche is a constrained data workflow that is easy to diff, deterministic in CI, and needs
no daemon or account. This product trades breadth for inspectability and a very small trust
boundary.

The GitHub repository was publicly reachable and showed no releases. The exact PyPI project
URL returned 404 during the audit. That is evidence only that no project page was visible at
the time; it does not reserve the distribution name or authorize publication.

## Product definition

### Target user and job

The primary user is a developer or release engineer who wants a small JSON transformation
or set of input assertions committed next to a project, without embedding Python code or
running an orchestration service. Typical jobs include preparing a release payload, shaping
fixture data, or enforcing a small precondition in a scriptable pipeline.

### Differentiators

- checked-in JSON instead of an external control plane;
- deterministic output suitable for tests and diffs;
- no runtime dependencies;
- no implicit environment, network, process, plugin, credential, or persistence access;
- bounded documents, nesting, collection sizes, and step counts.

### Supported checkout surface (package version remains 0.1.0; additions unreleased)

- workflow schema version `1`;
- ordered `set`, `assert`, `merge`, `pick`, `map`, `filter`, and `normalize` operations;
- templates rooted at `input`, `defaults`, and completed `steps`;
- CLI commands `validate`, `explain`, `run`, `test`, `schema`, and non-overwriting `init`;
- typed Python workflow, suite, explanation, and schema discovery APIs;
- bundled Draft 2020-12 structural schemas, JSON suite reports, and deterministic JUnit XML;
- UTF-8 JSON files and JSON-object input from a file or standard input.

### Explicit non-goals

Hosted APIs, browser UI, scheduling, durable recovery, retries, parallel execution, unbounded loops,
arbitrary expressions/code, third-party connectors, HTTP/webhooks, OAuth, credential
storage, secrets management, multi-tenancy, RBAC, databases, distributed workers,
marketplaces, AI agents, and compatibility with the unpublished prototype are not part of
0.1. Adding any side-effecting action requires a new threat model and an explicit capability
and credential boundary; it must not arrive as a generic URL or code escape hatch.

## Architecture and data flow

The package has the following responsibility layers:

1. `model.py` performs bounded UTF-8 JSON loading, duplicate-key rejection, structural
   validation, static template/reference checks, and defensive copying.
2. `runner.py` renders validated values, executes in-memory operations sequentially,
   and returns immutable result records.
3. `cli.py` maps files/stdin and exit codes onto the model and runner. `init` is the only
   command that writes a file and uses exclusive creation.
4. `__init__.py` exposes the deliberately small Python API; `__main__.py` and the console
   entry point call the same CLI.
5. `suite.py`, `schema.py`, and `explain.py` provide regression contracts, bundled
   structural schemas, and static dependency inventories; `_json.py` shares JSON equality.

Workflow input and defaults can flow into step output and final output. They cannot flow to
the environment, network, a subprocess, dynamic import, database, credential store, or
filesystem write inside the runner. The invoking shell can redirect stdout, which remains
under the caller's operating-system permissions and control.

## P0/P1 closure ledger

| Priority | Problem | Resolution and acceptance evidence | Status |
| --- | --- | --- | --- |
| P0 | No documented install-and-run path worked. | One `pyproject.toml`, correct src discovery, a real console function, `__main__`, editable install, and clean-wheel smoke procedure. | Closed locally |
| P0 | Tests did not parse or exercise a shipped journey. | Replaced with model/runner/CLI/API tests; 59 tests pass and branch-aware coverage is above the 95% gate. | Closed |
| P0 | Server authorization exposed other users' workflow configuration. | Removed the server, storage, auth, multi-user, and credential surfaces from package and docs. Static searches must find no FastAPI/Redis/PostgreSQL/private-monorepo imports. | Closed |
| P0 | Credential encryption failed open to plaintext. | Credential storage is not a 0.1 capability; encryption/storage modules and credential-bearing examples are removed. | Closed |
| P0 | License files and metadata contradicted one another. | Removed the custom BSL and proprietary stub, adopted the unmodified OSI-approved MPL-2.0, added SPDX/copyright notices, and aligned package metadata and contacts with Samsarix LLC. | Closed locally; ownership/counsel confirmation remains external |
| P1 | Claims, benchmarks, integration counts, and compliance language were unsupported. | README and docs now state only tested behavior and explicit non-goals. | Closed |
| P1 | Runtime depended on private `apps.backend` modules and many undeclared services. | Runtime is standard-library-only and imports no other Samsarix package. | Closed |
| P1 | Workflow parsing/execution had no defensible resource boundary. | 1 MiB document, 20-level nesting, 10,000-item collection, 50,000-value tree, 100,000-character string, 1,000-schema-step, and default 100-run-step limits; duplicate keys, parser recursion, non-finite numbers, and render amplification are rejected. | Closed |
| P1 | Packaging/build configuration drifted across `setup.py` and `pyproject.toml`. | `setup.py` removed; PEP 517 build and PEP 639-style license metadata live in `pyproject.toml`. | Closed |
| P1 | No CI or release gate existed. | Added Python 3.11–3.13 CI, format/lint/type/test gates, build/twine checks, and installed-wheel smoke commands. | Closed locally; hosted run pending |
| P1 | No security/reporting boundary existed. | Added `SECURITY.md`, bounded the engine, and documented disclosure limitations. | Closed for repository content |

## Compatibility and migration decision

This is an intentional breaking reset from the repository's claimed `1.0.0` to the first
truthful `0.1.0`. No compatibility shim is provided because the documented old public API
did not match importable code, the old server could not start independently, and carrying
its schemas forward would preserve unsafe credential and network assumptions.

The 2026-07-28 Samsarix rebrand is also intentionally complete: the distribution is
`samsarix-spirals`, the import package is `samsarix_spirals`, the command is
`samsarix-spirals`, and the public base exception is `SamsarixSpiralsError`. The legacy
names were never published as a supported `0.1` release, so compatibility aliases would
add ambiguity without preserving a real supported contract.

Users with prototype data should keep the old revision isolated, extract only non-secret
business rules, and manually express supported pure `set`/`assert` behavior in schema 1.
There is no automated importer. Do not load old action configuration into the new runner or
commit exported credentials.

## Verification ledger

Required local commands:

```console
python -m compileall -q src tests
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m bandit -q -r src
python -m pip_audit .
python -m pytest
python -m build
python -m twine check dist/*
samsarix-spirals validate examples/hello.json
samsarix-spirals run examples/hello.json --input examples/hello.input.json --compact
```

Historical initial-pass evidence (2026-07-28; see the revalidation above for current results):

- Python 3.11.9 and 3.13.14 local environments;
- Ruff formatting and lint: pass;
- strict mypy over 10 source files: pass;
- pytest: 59 pass on both local interpreters; Python 3.11 records 98.12%
  branch-aware coverage;
- both checked-in examples validate and run with expected JSON values;
- public import exposes only the documented API at version 0.1.0;
- Bandit source scan and a project-scoped `pip-audit`: pass with no reported findings;
- isolated PEP 517 sdist/wheel build and `twine check`: pass;
- a fresh virtual environment installed the wheel with `--no-deps`; isolated import,
  `python -m samsarix_spirals`, and installed console `validate`/`run` smoke checks pass;
- the wheel contains only the seven intended package files plus standard distribution
  metadata/license, while the sdist contains the documented source, tests, docs, and examples.

## Remaining blockers and follow-ups

Release-blocking external checks:

- observe the hosted Python 3.11, 3.12, and 3.13 matrix on the exact release commit;
- confirm the distribution name and package-index publisher ownership immediately before
  publication;
- have an authorized Samsarix LLC representative confirm that the company holds the rights
  needed to relicense all covered code under MPL-2.0, and obtain counsel review before the
  first public release if legal certainty is required;
- enable or verify GitHub private vulnerability reporting before advertising it as active;
- decide whether release tags/artifacts must be signed and establish the publisher account.

Non-blocking post-0.1 candidates:

- extend schema conformance coverage as new operations are added (structural schemas
  already ship in the wheel);
- add property-based parser/template tests if a runtime dependency policy permits it;
- add reproducible-build/SBOM attestations after a publishing system is chosen;
- consider JSON Pointer syntax in a future schema version for keys containing dots.

These items do not justify broadening 0.1 into a service or integration platform.

## Decision log

- **2026-07-28 — breaking reset approved by task mandate:** preserve the repository and
  history, but remove unsupported product surfaces rather than emulate fictional APIs.
- **2026-07-28 — local deterministic product selected:** market research showed mature
  hosted, durable, Python, and data orchestrators; the viable independent boundary is much
  smaller.
- **2026-07-28 — no runtime dependencies:** the two-operation core needs only the standard
  library, reducing installation and supply-chain surface.
- **2026-07-28 — no generic HTTP/code action:** these would defeat the product's primary
  security and differentiation boundary.
- **2026-07-28 — Samsarix identity adopted:** product, distribution, import package, CLI,
  public exception, ownership notices, and working contact addresses now use Samsarix LLC;
  the legacy GitHub slug remains an explicit external rename.
- **2026-07-28 — MPL-2.0 selected:** Mozilla's standard file-level copyleft replaces the
  inconsistent custom BSL. It preserves notices and distributed modifications to covered
  files while permitting combination with larger proprietary works.
