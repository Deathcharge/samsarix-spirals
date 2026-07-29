# Contributing

Samsarix Spirals 0.1 is intentionally small. Contributions should preserve its local,
deterministic, and side-effect-free execution boundary. Network actions, arbitrary
code execution, schedulers, credential storage, hosted services, and plugin loading
need a separate design and threat-model review before implementation.

## Development setup

Python 3.11 or newer is required.

```console
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

On macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python`.

## Required checks

Run these from the repository root before opening a pull request:

```console
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m bandit -q -r src
python -m pip_audit .
python -m pytest
python -m build
python -m twine check dist/*
```

Add tests for user-visible behavior and update `docs/WORKFLOW_FORMAT.md` whenever
the workflow contract changes. Do not include secrets or real customer input in
fixtures, issues, or logs.

By contributing, you represent that you have the right to submit the work and agree that
your contribution is licensed under the repository's MPL-2.0 terms. Copyright remains
with each contributor unless separately assigned. Contact `contact@samsarix.com` before
submitting work that requires a contributor agreement or different licensing terms.
