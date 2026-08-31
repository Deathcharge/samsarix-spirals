# Samsarix Spirals

Samsarix Spirals is a deterministic contract runner for JSON workflows that you can
review, regression-test, and keep beside your code. It is aimed at release gates,
agent-output contracts, configuration checks, and local data shaping—not hosted
automation or durable distributed orchestration.

Version `0.1.0` is a source release candidate. The package is not currently published
on PyPI, so install it from a checkout or a locally built wheel.

## What it does

- Validates a versioned JSON workflow before execution.
- Runs `set`, `assert`, `merge`, `pick`, `map`, `filter`, and `normalize` steps in a fixed order.
- Runs checked-in suites that prove expected outputs and expected failures.
- Renders values from `input`, `defaults`, and completed `steps`, with scoped `item`
  references inside list transformations.
- Emits deterministic JSON with no timestamps, random IDs, or hidden state.
- Performs no network requests, subprocess execution, credential storage, or imports
  from another Samsarix repository.

Samsarix Spirals is not a Zapier, n8n, Temporal, Prefect, Dagster, Dagger, or CUE
replacement. Its advantage is a deliberately small, hermetic contract surface: no UI,
server, scheduler, connectors, code execution, network access, or persistence.

## Install from a checkout

Python 3.11 or newer is required.

```console
git clone https://github.com/Deathcharge/samsarix-spirals.git
cd samsarix-spirals
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

On macOS or Linux, use `.venv/bin/python` in place of `.venv\Scripts\python`.

## Run the example

```console
.venv\Scripts\samsarix-spirals validate examples/hello.json
.venv\Scripts\samsarix-spirals explain examples/agent-tool-result.json
.venv\Scripts\samsarix-spirals run examples/hello.json --input examples/hello.input.json
.venv\Scripts\samsarix-spirals test examples/release-policy.json examples/release-policy.suite.json
.venv\Scripts\samsarix-spirals test examples/agent-tool-result.json examples/agent-tool-result.suite.json
.venv\Scripts\samsarix-spirals schema workflow --compact
```

The output's `output` field is:

```json
{
  "message": "Hello, Ada!",
  "name": "Ada"
}
```

Use `explain` during review to see every referenced input/default path and each step's
direct dependencies without providing input or executing the workflow. The JSON report
contains paths and operation names, not resolved values:

```console
samsarix-spirals explain workflow.json --compact
```

Create a starter file without overwriting an existing path:

```console
.venv\Scripts\samsarix-spirals init my-workflow.json
```

Input can also come from standard input:

```console
echo {"name":"Ada"} | .venv\Scripts\samsarix-spirals run examples/hello.json --input - --compact
```

PowerShell users should prefer `'{"name":"Ada"}' | ...` so quoting is preserved.

## Pass a final result to another system

Use `--output-only` when piping a result to a downstream consumer:

```console
samsarix-spirals run examples/agent-tool-result.json --input examples/agent-tool-result.input.json --output-only --compact
```

This emits the raw final JSON value, without the `status`, `workflow`, or `steps` wrapper.
The example keeps only the ticket fields and trusted policy metadata; private extra
fields and metadata overrides from `result` do not reach this output. `approved` must be
the JSON boolean `true`, supplied by a trusted caller, not by the agent itself. This tool
checks data; it does not authenticate approvals or verify claims about an external system.

Without `--output-only`, `run` preserves the full diagnostic step trace. That trace can
contain values removed by a later `pick`; **do not send it to a downstream consumer as a
redacted result**. In Python, consume `result.output`, not `result.to_dict()` or
`result.steps`, for this boundary. The flag does not scrub final values or stderr:
workflow authors must review allowed fields and avoid secrets in assertion messages.

## Regression suites

A suite stores named inputs beside exact expected outputs or expected execution errors.
The `test` command runs every case, reports all mismatches, and exits `1` if the contract
has changed. Reports describe the mismatch without echoing input or output values, which
reduces accidental disclosure of fixture data in CI logs.

```console
samsarix-spirals test workflow.json workflow.suite.json
samsarix-spirals test workflow.json workflow.suite.json --json --compact
samsarix-spirals test workflow.json workflow.suite.json --junit
```

See [`examples/release-policy.suite.json`](examples/release-policy.suite.json) for a
release approval gate with both successful and rejected cases.
[`examples/agent-tool-result.suite.json`](examples/agent-tool-result.suite.json) proves
that an approved agent result is enriched, restricted to an explicit key allowlist, and
rejected when required output is absent. Extra reasoning and credential-shaped fields
never reach the final workflow output (use `--output-only` to omit intermediate traces).
[`examples/repository-policy.suite.json`](examples/repository-policy.suite.json) models a
production-repository security baseline and includes adversarial boolean/numeric,
missing-field, public-visibility, and secret-shaped extra-field fixtures.

## JSON Schemas and CI reports

Draft 2020-12 schemas for workflow and suite version `1` ship inside every wheel. Print
them without locating package files:

```console
samsarix-spirals schema workflow
samsarix-spirals schema suite --compact
```

The schemas provide editor completion and structural validation. Runtime validation is
still authoritative for document byte/depth budgets, unique IDs and names, and semantic
template references. The schema `$id` values are stable identifiers; they do not promise
that a public schema host is deployed yet.

For CI systems that ingest JUnit XML, use `--junit`. The deterministic report contains
suite and case names plus non-sensitive mismatch categories, but never fixture inputs,
expected outputs, or actual outputs.

## Prepare a batch for CI

The release-target example filters enabled records, projects their names, and applies
ordered ASCII trim/lowercase transforms:

```console
samsarix-spirals run examples/release-targets.json --input examples/release-targets.input.json --output-only --compact
samsarix-spirals test examples/release-targets.json examples/release-targets.suite.json
```

The final value is `["linux-x64", "windows-x64"]`. Empty input returns `[]`; missing
required record fields or non-string target names fail with an attributed error. Order
and duplicates are preserved. This example prepares data only: a downstream job must
still validate allowed target names, authorization, uniqueness, and shell-safe usage.
Normalization is not sanitization, and `filter` preserves whole selected records in its
trace. Use `--output-only` when only the projected names should leave the process.

See the [list operation contracts](docs/WORKFLOW_FORMAT.md#map) for scope and limits.

## Python API

```python
from samsarix_spirals import explain_workflow, load_workflow, run_workflow

workflow = load_workflow("examples/hello.json")
print(explain_workflow(workflow).input_paths)
result = run_workflow(workflow, {"name": "Ada"})
print(result.output)
```

Bundled schemas and suite reports are also available through `get_schema` and
`suite_result_to_junit_xml` in the typed Python API.

The pre-1.0 API can change between minor releases. Workflow schema changes will use the
top-level `schema_version` field and be documented in the changelog.

## Failure behavior

- CLI exit `0`: validation or execution succeeded.
- CLI exit `1`: a valid workflow failed during execution, such as a false assertion.
- CLI exit `2`: arguments, files, JSON, or workflow structure were invalid.

Execution is fail-fast. A failed assertion produces no success document on standard
output, and later steps do not run.

Rendered arguments/final values have a 4 MiB encoded-payload budget, and retained step
outputs plus final output have a combined 16 MiB budget. Budget failures also exit `1`
with no partial stdout. See [limits and accounting](docs/WORKFLOW_FORMAT.md#encoded-payload-budgets)
for Unicode, repeated-output, and memory-limit details.

## Documentation

- [Pinned GitHub Action and pre-commit integration](docs/REPOSITORY_INTEGRATIONS.md)
- [Workflow format](docs/WORKFLOW_FORMAT.md)
- [Compatibility and deprecation policy](docs/COMPATIBILITY.md)
- [Competitive position and use cases](docs/COMPETITIVE_POSITIONING.md)
- [Productization record](docs/PRODUCTIZATION.md)
- [Release process](docs/RELEASING.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Project status and release boundary

The core journey—install, validate, explain, run, regression-test, inspect output—has
local automated coverage.
Before publishing, a maintainer still needs to observe the GitHub Actions matrix on the
target commit, confirm the distribution name is still available, create the tag, and
publish through an owned package index account. Those external steps are intentionally
not claimed as complete here.

The repository, product, Python distribution, import package, and console command now use
the Samsarix identity.

## License

The source is available under the OSI-approved [Mozilla Public License 2.0](LICENSE).
MPL 2.0 keeps modifications to covered Samsarix files open when they are distributed,
while allowing those files to be combined with a larger proprietary work. Copyright and
brand ownership are recorded in [NOTICE](NOTICE). The MPL does not grant rights to use
Samsarix names or logos as trademarks.

## Contact

- General and licensing questions: `contact@samsarix.com`
- Product support and private security reports: `support@samsarix.com`
