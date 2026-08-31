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
python -m bandit -q tools/release_check.py
python -m pip_audit .
python -m pip_audit -r requirements/build.lock
python -m pytest
python -m build
python -m twine check dist/*
```

The commands above remain development/package-shape checks. Their default isolated
build resolves the version ranges in `pyproject.toml`; it is **not** the pinned candidate
build. Commit reviewed changes before the next step. Do not build a release from dirty
source or from a PR's synthetic merge commit.

## 3. Produce candidate artifacts from committed source

Use a fresh builder environment with Python 3.11 or newer and Git. Keep both the builder
and candidate directory outside the checkout. For example, from the repository root on
Windows PowerShell:

```powershell
$releaseWork = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ('samsarix-release-' + [guid]::NewGuid()))
python -m venv (Join-Path $releaseWork.FullName 'builder')
if ($LASTEXITCODE -ne 0) { throw 'Builder creation failed' }
$builderPython = Join-Path $releaseWork.FullName 'builder/Scripts/python.exe'
& $builderPython -m pip install --require-hashes --only-binary=:all: -r requirements/build.lock
if ($LASTEXITCODE -ne 0) { throw 'Pinned tool installation failed' }
& $builderPython -I tools/release_check.py --output-dir (Join-Path $releaseWork.FullName 'candidate')
if ($LASTEXITCODE -ne 0) { throw 'Candidate verification failed' }
```

On Linux/macOS with a POSIX shell:

```console
release_work=$(mktemp -d) &&
python3 -m venv "$release_work/builder" &&
"$release_work/builder/bin/python" -m pip install --require-hashes --only-binary=:all: -r requirements/build.lock &&
"$release_work/builder/bin/python" -I tools/release_check.py --output-dir "$release_work/candidate"
```

The helper requires a clean Git checkout (including untracked files), verifies the six
installed tool versions and `pip check`, and exports the exact commit with `git archive`.
Ignored build caches and local files cannot enter that export. It builds twice in separate
temporary source directories with `SOURCE_DATE_EPOCH` set to the commit timestamp and
`build --no-isolation`, retaining the frontend's dependency checks. Each build creates a
source distribution and then builds its wheel from that source distribution. Different
wheel names or bytes fail verification. Source-archive byte equality is measured and
reported, **not required**.

Before retaining any candidate, the helper installs the first wheel into a third, fresh
environment using `--no-index --no-deps`, then runs the committed `installed_smoke.py`.
That checks all example suites, output-only behavior, numeric approval rejection, and
JSON/JUnit diagnostic contracts against the installed package using isolated imports.
The source checkout must still be clean and at the same commit afterward. Child commands
have 180-second timeouts; this trusted maintainer tool is not a workflow operation or an
untrusted-build sandbox.

On exit code 0, the new candidate directory contains exactly:

- the wheel and source distribution;
- `SHA256SUMS`, covering those two artifact files;
- `release-check.json`, with the source revision, lock digest, tool versions, Python/OS/
  zlib environment, byte comparisons, smoke outcome, artifact sizes, and SHA-256 hashes.

It never overwrites an existing output directory. Treat any nonzero exit as failure,
even if an I/O failure leaves a partial output directory. Keep verified artifacts and
their evidence together; do not replace the wheel by rebuilding during publication.
Review candidate metadata with the development environment's `python -m twine check`
against these two actual candidate paths, not stale `dist/` files.

### Scope of the evidence

This verifies two builds **within one environment**, not bit-for-bit agreement across
different operating systems, Python versions, or future toolchains. Source archives can
differ despite identical wheels. The lock covers six build packages, not Python, pip,
the OS, every development dependency, or the inherited build environment. The helper's
version check is not an installed-file integrity check: use the fresh hash-checked install
shown above. There are no runtime dependencies, and ordinary source installs continue to
use the compatible build-system ranges in `pyproject.toml`.

Checksums detect changed bytes relative to trusted evidence; they do not authenticate a
publisher. This report is unsigned, not an attestation, signature, SBOM, SLSA certification,
or proof of a hermetic/offline build. Publisher-controlled signing/provenance remains an
explicit later decision. See [pip's secure installation guidance](https://pip.pypa.io/en/stable/topics/secure-installs/)
and [PyPA build's isolation/reproducibility guidance](https://build.pypa.io/en/latest/explanation/how-it-works.html).

Update `requirements/build.lock` deliberately: review upstream versions, obtain wheel
SHA-256 hashes from the official package index, include transitive dependencies for all
supported builder platforms, and rerun the hash-checked install, dependency audit, and
three-platform candidate jobs. Do not silently refresh pins during a release build.

### Hosted candidate retention

CI runs the candidate check on Linux, Windows, and macOS with Python 3.11 after the test
matrix passes. It retains each successful job's four files for 14 days as
`candidate-<OS>-<checkout SHA>`. These are GitHub Actions artifacts, **not published
packages or releases**. PR artifacts identify the synthetic merge revision; use the
post-merge default-branch run for a release candidate. Require the entire CI run and
consumer-integration run to pass, not just one successful artifact upload. Download the
chosen artifact bundle, confirm its `source_revision`, and compare the file hashes with
its report before any authorized publication. Artifact retention is temporary; an
authorized release process must preserve the chosen evidence with its release.

## 4. Require external evidence

- Observe a successful GitHub Actions run for the exact candidate commit on every Python
  version in the matrix.
- Review the built wheel contents and metadata.
- Confirm there are no unexpected tracked or generated files and no secrets.
- Review `docs/PRODUCTIZATION.md` for unresolved release blockers.

## 5. Publish intentionally

Only a maintainer with authority over the repository, tag, and package index should:

1. create a signed `vX.Y.Z` tag;
2. create release notes from the changelog;
3. publish the already verified artifacts through an owned trusted-publishing setup;
4. download the published wheel into a fresh environment and repeat the smoke test.

This repository does not contain an automatic publish workflow. Adding one requires
maintainer approval and an explicit package-index ownership decision.
