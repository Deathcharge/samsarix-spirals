# Repository integrations

Use these integrations to check a workflow and its regression suite alongside application
code. They validate fixtures, not live repository settings or real publishing permissions.
The examples pin the verified source candidate at commit
`4ef5f51ef12778a72825b2c687028454d5fd3858`; review and update that full SHA deliberately.
No package-index publication is required.

## GitHub Action

Copy `examples/release-targets.json` and `examples/release-targets.suite.json` into the
consumer repository (or provide your own workflow/suite pair). Then add:

```yaml
name: Workflow contracts
on: [push, pull_request]
permissions:
  contents: read
jobs:
  contracts:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: Deathcharge/samsarix-spirals@4ef5f51ef12778a72825b2c687028454d5fd3858
        with:
          workflow: examples/release-targets.json
          suite: examples/release-targets.suite.json
          python-version: '3.13'
```

The Action supports GitHub-hosted Linux, Windows, and macOS runners with Bash. Paths are
relative to `GITHUB_WORKSPACE`, may contain spaces, and must resolve to regular files
inside that workspace. Absolute paths within the workspace also work; directory paths,
missing files, traversal outside the workspace, and symlinks pointing outside are rejected.
Do not race filesystem mutations against a running check.

The Action provisions Python using a SHA-pinned `actions/setup-python`, then runs the
library from its own pinned source under Python isolated mode. It does not install the
consumer project, use consumer `PYTHONPATH`, accept a shell command, or require a token
input. Path inputs pass through environment variables, not generated shell source.
Provisioning needs network access unless runner caches suffice; workflow execution itself
remains local. Pinning source does not freeze the hosted runner image or Python patch
version. Self-hosted runners must meet setup-python's runtime requirements and provide Bash.

A successful suite succeeds the step. A mismatch or invalid document fails it. Do not
set `continue-on-error` on a required contract gate. Reports contain suite/case names,
counts, and generic mismatch reasons, not fixture inputs, expected values, or workflow
outputs. Keep names non-sensitive. Invalid-document diagnostics may contain field names
and paths. All report text is JSON-escaped; GitHub error annotations also escape workflow
command delimiters. At most ten case annotations plus an overflow summary are emitted.
Annotations identify failed cases and actual failing step IDs when execution provides
one, but not JSON source lines. Final-output/run-level errors have no invented step ID.
The JSON report also includes stable case `failure_code` values; see
[failure diagnostics](WORKFLOW_FORMAT.md#failure-diagnostics) for the complete contract.

Use a normal `pull_request` workflow with read-only permissions. Avoid granting secrets
or write tokens merely to run contracts, and do not combine untrusted code execution
with privileged `pull_request_target` workflows. Like any Action, the pinned action code
itself is trusted executable code; the JSON workflow is not a process-isolation sandbox.

## pre-commit

Install pre-commit (the integration tests use `pre-commit==4.6.1`) and ensure Python 3.11
or newer is available. Add this to the consumer's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Deathcharge/samsarix-spirals
    rev: 4ef5f51ef12778a72825b2c687028454d5fd3858
    hooks:
      - id: samsarix-spirals-test
        name: Release target contract
        language_version: python3.13
        args: [examples/release-targets.json, examples/release-targets.suite.json]
```

Select an installed Python version; `python3.13` is a version name, not a Windows
executable path. Use one hook configuration per workflow/suite pair. Filenames supplied
by Git are not appended: the hook always checks the configured pair, even on commits
that change neither file. Paths are relative to the consumer repository and are passed
as separate arguments, so spaces do not require shell quoting inside YAML strings.

```console
python -m pip install pre-commit==4.6.1
python -m pre_commit validate-config
python -m pre_commit run --all-files
python -m pre_commit install
```

The first run clones the pinned repository and builds the Python hook in pre-commit's
managed environment. Build tooling may be downloaded; review the hook configuration and
do not add untrusted `additional_dependencies`. The runner itself has no runtime
dependencies. This is not a locked/offline build environment.

The hook does not rewrite files. A mismatch or invalid JSON blocks the commit. Use the
regular CLI to investigate, correct the workflow/fixture, and rerun. Local hooks are
bypassable; the CI check should remain authoritative. No hook is automatically installed
into this checkout by these instructions or by the integration test.

## CI-oriented command and verification

Installed packages also expose:

```console
samsarix-spirals-ci examples/release-targets.json examples/release-targets.suite.json
```

It emits one JSON report line and exits `0` for success, `1` for a contract mismatch,
or `2` for invalid documents/arguments. `--github-annotations` adds escaped annotations;
`--workspace PATH` restricts input paths as described above. pre-commit maps any failing
hook to its own nonzero exit status. The existing `samsarix-spirals test` CLI is unchanged.

Maintainers can run `python tests/integration_smoke.py` after committing the implementation.
It creates a temporary Git consumer and hook cache, installs the committed hook through
real pre-commit, verifies success, deliberately wrong expectations, and invalid JSON, then
removes only those temporary fixtures. `Consumer integrations` CI exercises the actual
composite action and fresh hook on all three hosted OS families. Run
`python tests/integration_smoke.py --documented-pin` to test the exact documented
pre-commit revision, including its failure codes and step context. The commit must be
present locally; CI fetches history for this check. Pin-consistency tests keep the Action,
hook, evaluation guide and public consumer CI examples aligned. Synthetic consumers
prove integration behavior, not independent adoption or product-market fit.

For a first evaluation and an optional, privacy-conscious feedback report, see
[Evaluate in your repository](EVALUATION.md).

References: [GitHub composite actions](https://docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action),
[workflow-command escaping](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands),
and [pre-commit hook contracts](https://pre-commit.com/#creating-new-hooks).
