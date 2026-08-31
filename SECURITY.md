# Security policy

## Supported versions

The latest `0.1.x` release is supported. Pre-productization `1.0.0` repository
snapshots are not supported and should not be deployed.

## Reporting a vulnerability

Email `support@samsarix.com` with the subject `Samsarix Spirals security report`, or use
the repository's **Security → Report a vulnerability** flow if private reporting is
enabled. Do not include exploit details, secrets, or customer data in a public issue.

Include the affected version, platform, minimal reproduction, impact, and any proposed
mitigation. Samsarix LLC does not currently promise a response-time SLA.

## Security boundary

Samsarix Spirals 0.1 reads local JSON documents and returns local JSON output. Its runner:

- performs no network, subprocess, dynamic import, `eval`, or persistence operations;
- accepts only the built-in `set`, `assert`, `merge`, and `pick` operations;
- rejects duplicate JSON keys, non-finite numbers, excessive nesting, files over 1 MiB,
  workflows over 1,000 steps, strings over 100,000 characters, and JSON trees over
  50,000 values;
- caps a normal run at 100 steps unless the caller explicitly raises the limit.

The tool runs with the invoking user's filesystem permissions. Treat workflow and input
files as data, review output destinations chosen by shell redirection, and do not put
secrets in committed workflow defaults or examples.

`run` emits intermediate step outputs by default for diagnostics. `pick` restricts the
final selected object, not earlier trace entries or nested children of an allowed key.
For a downstream data boundary, use `run --output-only` or the Python `RunResult.output`
attribute. These interfaces omit the trace; they do not scrub values explicitly selected
by the workflow or sensitive text in custom assertion errors on stderr.

Workflows and their policy defaults must be reviewed by the operator. Input can be
untrusted, but approval metadata must come from a trusted caller; the runner cannot
authenticate the producer or verify external repository settings. Boolean approval gates
should use `equals` with `true` or `false`, not `truthy`/`falsy`. Apply trusted metadata
last in a `merge` so an untrusted object cannot override it.
