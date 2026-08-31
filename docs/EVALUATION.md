# Evaluate in your repository

This is an opt-in source-candidate trial, not a production-readiness claim. Use it to
answer one question: is a small, checked-in JSON contract easier for your team to review
and maintain than its current script? A result of **not useful** is valid feedback.

Start with non-sensitive fixtures, no publishing credentials, and no live side effects.
Keep your existing checks authoritative during the trial. Do not use fixture assertions
as evidence that real approvals, repository settings, or external systems are trustworthy.

## 1. Try a known, pinned contract

Python 3.11 or newer and Git are required. Run this in a new directory, not over an
existing checkout. The full commit matches the [integration examples](REPOSITORY_INTEGRATIONS.md)
and has passed hosted checks; it is not a published package version or signed release.

```console
git clone https://github.com/Deathcharge/samsarix-spirals.git
cd samsarix-spirals
git checkout --detach 4ef5f51ef12778a72825b2c687028454d5fd3858
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m samsarix_spirals validate examples/release-targets.json
.venv\Scripts\python -m samsarix_spirals test examples/release-targets.json examples/release-targets.suite.json --json --compact
.venv\Scripts\python -m samsarix_spirals run examples/release-targets.json --input examples/release-targets.input.json --output-only --compact
```

On macOS/Linux, replace every `.venv\Scripts\python` with `.venv/bin/python`; use
`python3` to create the environment if `python` is unavailable. Stop and investigate any
unexpected nonzero exit before proceeding. No environment activation is needed.

Expected results: validation succeeds; the suite reports eight passed cases, zero
failures, and `successful: true`; the final command emits
`["linux-x64", "windows-x64"]`. The workflow filters enabled records, selects their
names, and trims/lowercases ASCII text. It preserves ordering and duplicates. It does
not authorize these target names or execute a release.

Installation can download build tools; pinning this source does not pin Python, the OS,
or the install environment. For hash-pinned candidate artifacts, use the maintainer
[release process](RELEASING.md). The workflow runtime itself has no runtime dependencies,
network access, subprocess execution or credential storage.

## 2. See a contract fail before trusting a green check

Create a **new** `evaluation.suite.local.json` file in the checkout with the following
non-sensitive fixture. Do not overwrite an existing file. Its `.local.json` suffix is
ignored by this checkout's Git configuration; other repositories need their own policy.

```json
{
  "suite_version": 1,
  "name": "evaluation",
  "cases": [
    {
      "name": "deliberate output mismatch",
      "input": {"targets": [{"name": " LINUX-X64 ", "enabled": true}]},
      "expect": {"output": ["deliberately-wrong"]}
    }
  ]
}
```

```console
.venv\Scripts\python -m samsarix_spirals test examples/release-targets.json evaluation.suite.local.json --json --compact
```

Expected exit: **1**, with `failure_code: "output_mismatch"`, one failed case and
`successful: false`. There is no `step_id`: execution completed and the final expectation
was wrong. Change the expectation to `["linux-x64"]` and rerun; it should pass with exit 0.

Then replace only this disposable fixture's contents with:

```json
{
  "suite_version": 1,
  "name": "evaluation",
  "cases": [
    {
      "name": "enabled record needs a name",
      "input": {"targets": [{"enabled": true}]},
      "expect": {"output": []}
    }
  ]
}
```

Run the same command. Expected exit: **1**, `failure_code: "unexpected_execution_error"`
and `step_id: "names"`. The enabled record reaches the projection step but has no name.
Reports must not print the input values or the underlying template-error message. Invalid
JSON instead exits 2; that is an invalid fixture, not an ordinary contract mismatch.

These deliberate failures demonstrate diagnostics, not flaws in the example workflow.
The guide's fixtures are regression-tested. Remove only the disposable file when finished.

## 3. Adapt one real rule, then evaluate CI

Choose one existing release-manifest, agent-result or configuration check that needs only
the [supported operations](WORKFLOW_FORMAT.md). Do not migrate a scheduler, network call,
secret, nested loop, or arbitrary script into a JSON workaround.

1. Keep the original script/check and write down its intended input/output behavior.
2. Copy a suitable workflow and suite into a reviewable location in your own repository.
   Add a positive case, an ordinary empty case, and realistic rejected inputs. Redact
   customer data; keep case names and assertion messages non-sensitive too.
3. Have the rule's owner review both the workflow and its fixtures. Approval metadata
   must come from a trusted caller, not an agent or other untrusted input producer.
4. Run the suite locally, then use the exact pinned [Action or pre-commit configuration](REPOSITORY_INTEGRATIONS.md).
   No package-index account is needed. Do not remove an existing required check merely
   to try this candidate. Hook installation and CI changes remain the consumer's choice.
5. Check a deliberately wrong expectation in a disposable branch: the CI job must fail.
   Restore the correct fixture and verify a green run before merging consumer changes.
   Never use `continue-on-error` on a gate you intend to require.
6. Compare review effort, diagnostic usefulness, maintenance cost and lost capabilities
   with the original check. Keep Spirals only if it earns its place for the rule's owners.

Only final `--output-only` values should feed a later consumer. A full trace can retain
fields that were subsequently removed, and allowed nested values are not automatically
scrubbed. Keep any side-effecting process, credentials and authorization outside Spirals.

For rollback, restore the prior reviewed CI/hook configuration through normal change
control and keep the original check active. Record the candidate commit and failing
case category first, without copying private values into public logs. Rolling back this
local contract tool does not undo actions performed by downstream systems.

## 4. Record evidence, including unsuccessful trials

There is no telemetry or automatic submission. You can keep the following record
privately. If you choose to share a public report, use the repository's **New issue →
Evaluation report** template. Do not include private repository URLs, secrets, customer
fixtures or security exploit details. For private support/security reports use
`support@samsarix.com`; no response-time SLA is promised.

- Source commit, OS/Python version and installation method.
- The real rule and the previous approach; who owns/reviews it (a role is enough).
- Synthetic trial versus real consumer; whether its ownership is independent of Samsarix.
- First and last observed CI dates, actual run counts, failures and unexplained changes.
  Count workflow-suite invocations, not individual cases, benchmark loops or retries as
  separate independent evidence. Link only runs you are authorized to disclose.
- A written before/after assessment, including workarounds, time spent and reasons to
  keep, stop or defer adoption. Optional usability observations do not establish demand.

The [roadmap's adoption gates](../ROADMAP.md#adoption-gates) still require three
independently owned CI consumers, a 30-day flagship record, 100 real executions, a written
before/after evaluation and published release/rollback evidence. Unknowns stay unknown;
a self-reported trial is not independently verified just because an issue exists. A
maintainer must review the evidence and update the productization record before making
any adoption or production-readiness claim. Do not contact or enroll anyone automatically.
