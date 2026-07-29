# Samsarix Spirals

Samsarix Spirals is a small, deterministic runner for JSON workflows that you can review,
test, and keep beside your code. It is aimed at local validation and data shaping—not
hosted automation, third-party integrations, or durable distributed orchestration.

Version `0.1.0` is a source release candidate. The package is not currently published
on PyPI, so install it from a checkout or a locally built wheel.

## What it does

- Validates a versioned JSON workflow before execution.
- Runs `set` and `assert` steps in a fixed order.
- Renders values from `input`, `defaults`, and completed `steps`.
- Emits deterministic JSON with no timestamps, random IDs, or hidden state.
- Performs no network requests, subprocess execution, credential storage, or imports
  from another Samsarix repository.

Samsarix Spirals is not a Zapier, n8n, Temporal, Prefect, or Dagster replacement. It has no
UI, server, scheduler, retries, connectors, parallelism, or persistence in this release.

## Install from a checkout

Python 3.11 or newer is required.

```console
git clone https://github.com/Deathcharge/samsarix-spirals.git
cd helix-spirals
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

On macOS or Linux, use `.venv/bin/python` in place of `.venv\Scripts\python`.

## Run the example

```console
.venv\Scripts\samsarix-spirals validate examples/hello.json
.venv\Scripts\samsarix-spirals run examples/hello.json --input examples/hello.input.json
```

The output's `output` field is:

```json
{
  "message": "Hello, Ada!",
  "name": "Ada"
}
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

## Python API

```python
from samsarix_spirals import load_workflow, run_workflow

workflow = load_workflow("examples/hello.json")
result = run_workflow(workflow, {"name": "Ada"})
print(result.output)
```

The pre-1.0 API can change between minor releases. Workflow schema changes will use the
top-level `schema_version` field and be documented in the changelog.

## Failure behavior

- CLI exit `0`: validation or execution succeeded.
- CLI exit `1`: a valid workflow failed during execution, such as a false assertion.
- CLI exit `2`: arguments, files, JSON, or workflow structure were invalid.

Execution is fail-fast. A failed assertion produces no success document on standard
output, and later steps do not run.

## Documentation

- [Workflow format](docs/WORKFLOW_FORMAT.md)
- [Productization record](docs/PRODUCTIZATION.md)
- [Release process](docs/RELEASING.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Project status and release boundary

The 0.1 core journey—install, validate, run, inspect output—has local automated coverage.
Before publishing, a maintainer still needs to observe the GitHub Actions matrix on the
target commit, confirm the distribution name is still available, create the tag, and
publish through an owned package index account. Those external steps are intentionally
not claimed as complete here.

The GitHub repository currently retains its legacy `helix-spirals` slug. The product,
Python distribution, import package, and console command use the Samsarix name.

## License

The source is available under the OSI-approved [Mozilla Public License 2.0](LICENSE).
MPL 2.0 keeps modifications to covered Samsarix files open when they are distributed,
while allowing those files to be combined with a larger proprietary work. Copyright and
brand ownership are recorded in [NOTICE](NOTICE). The MPL does not grant rights to use
Samsarix names or logos as trademarks.

## Contact

- General and licensing questions: `contact@samsarix.com`
- Product support and private security reports: `support@samsarix.com`
