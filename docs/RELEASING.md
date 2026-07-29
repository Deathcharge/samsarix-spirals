# Releasing

This is a maintainer checklist, not evidence that a release has already been published.

## 1. Prepare

1. Confirm the version matches in `pyproject.toml`, `src/samsarix_spirals/__init__.py`,
   and `CHANGELOG.md`.
2. Confirm the license parameters and package metadata still reflect the intended terms.
3. Confirm the `samsarix-spirals` distribution name is available to the publisher. A 404
   was observed on PyPI during the 2026-07-28 audit, but availability is not reserved.
4. Start from a clean checkout of the candidate commit on a supported Python version.

## 2. Verify

```console
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m bandit -q -r src
python -m pip_audit .
python -m pytest
python -m build
python -m twine check dist/*
```

Create a new virtual environment, install only the wheel, and smoke-test the installed
copy rather than the source tree:

```console
python -m venv .release-venv
.release-venv\Scripts\python -m pip install --no-deps dist/samsarix_spirals-0.1.0-py3-none-any.whl
.release-venv\Scripts\samsarix-spirals validate examples/hello.json
.release-venv\Scripts\samsarix-spirals run examples/hello.json --input examples/hello.input.json
```

Remove the disposable environment afterward. On macOS or Linux, use `.release-venv/bin/`.

## 3. Require external evidence

- Observe a successful GitHub Actions run for the exact candidate commit on every Python
  version in the matrix.
- Review the built wheel contents and metadata.
- Confirm there are no unexpected tracked or generated files and no secrets.
- Review `docs/PRODUCTIZATION.md` for unresolved release blockers.

## 4. Publish intentionally

Only a maintainer with authority over the repository, tag, and package index should:

1. create a signed `vX.Y.Z` tag;
2. create release notes from the changelog;
3. publish the already verified artifacts through an owned trusted-publishing setup;
4. download the published wheel into a fresh environment and repeat the smoke test.

This repository does not contain an automatic publish workflow. Adding one requires
maintainer approval and an explicit package-index ownership decision.
