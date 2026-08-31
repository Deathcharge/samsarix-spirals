# Compatibility and deprecation policy

Samsarix Spirals uses semantic versioning for the Python distribution and explicit
version fields for machine-readable documents. The project is still alpha, but checked-in
workflow contracts need a narrower and more predictable change boundary than a typical
pre-1.0 library.

## Compatibility surfaces

| Surface | Compatibility rule before 1.0 |
| --- | --- |
| Workflow `schema_version: 1` | Existing valid documents retain their syntax and operation semantics across `0.x` releases. A breaking document change requires a new schema version. |
| Suite `suite_version: 1` | Existing valid suites retain their syntax and expectation semantics across `0.x` releases. A breaking document change requires a new suite version. |
| Explanation `explain_version: 1` | Existing fields keep their meaning. New optional fields may be added in a minor release; removing or redefining fields requires a new explanation version. |
| CLI | Existing command names, success/error exit classes (`0`, `1`, `2`), and documented flags remain compatible within a minor release line. New commands and optional flags may be added. |
| Python API | Patch releases are compatible. Until 1.0, a minor release may change public Python names or signatures when recorded in the changelog and migration notes. |
| Suite JSON reports | Existing fields retain their meaning. Optional fields may be added; readers should tolerate unknown fields and failure codes. `failure_code` values retain their documented meanings within the current minor line. |
| Human-readable diagnostics | Wording may improve at any release. Automation must use exit codes, JSON/JUnit reports, and step IDs rather than matching complete human messages. |

Adding an operation, assertion operator, or optional document field is backward-compatible
for existing version 1 documents. Changing an existing operation's output, precedence,
type rules, failure behavior, or determinism is not. Tightening a limit is breaking unless
required to address an actively exploitable security or resource-exhaustion issue.

Bug fixes that make behavior match the documented contract are allowed in patch releases.
If callers may have relied on the defect, the changelog must identify the corrected case.

## Python result ownership

Results from `run_workflow` have frozen record fields but mutable JSON dictionaries and
lists. The final output, each step output, and each `to_dict()` export own detached
mutable trees. Mutating one does not mutate another, the supplied input, validated
workflow data, or a later run. Repeated template occurrences are detached too.

This is an ownership contract, not deep immutability or a sandbox for arbitrary Python
objects. Construct workflows with the public validation factories and do not mutate
validated internals during execution. Private implementation indexes may share trees
while a run is in progress; they are not public interfaces.

## Deprecation process

There are no deprecated workflow features today. If one is introduced, maintainers will:

1. document the replacement and first deprecated release in the changelog;
2. keep the old behavior working for at least one subsequent minor release;
3. emit a concise standard-error warning from CLI paths that load the deprecated feature,
   without including workflow or input values;
4. provide a before/after migration fixture; and
5. remove or redefine document behavior only under a new document version.

The waiting period may be shortened only for a high-impact security issue. In that case,
the security advisory and release notes must explain the incompatibility and safest
migration path.

## Version support

The repository tests every pull request on the Python versions listed in `pyproject.toml`
and the CI matrix. Dropping a Python version requires a minor release, an updated
`requires-python`, and changelog notice. Release artifacts are supported only when built
from a tagged commit using the documented release process.

Schema identifiers are stable identifiers, not proof that a public schema-hosting service
exists. The schemas bundled in the installed wheel are the authoritative published copies.
