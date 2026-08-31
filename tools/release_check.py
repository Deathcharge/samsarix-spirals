# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Build twice from clean committed source, smoke-test, then retain candidate evidence.

Maintainer tooling executes trusted build backends in child processes, never JSON
workflow code. This is not an untrusted-source sandbox or a package publisher.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil

# Explicit maintainer build tool; no workflow-controlled executable.
import subprocess  # nosec B404
import sys
import tarfile
import zlib
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
COMMAND_TIMEOUT = 180
LOCK_LINE = re.compile(r"([a-z][a-z0-9-]*)==([^\s]+) --hash=sha256:([a-f0-9]{64})")


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def locked_versions(path):
    """Keep the lock grammar deliberately small and reject ambiguous requirements."""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = LOCK_LINE.fullmatch(line)
        if match is None or match[1] in result:
            raise ValueError("invalid or duplicate requirement in build lock")
        result[match[1]] = match[2]
    if not result:
        raise ValueError("build lock must not be empty")
    return result


def check_toolchain(path):
    """Verify versions; pip's hash-checking install separately verifies downloaded wheels."""
    expected = locked_versions(path)
    for name, version in expected.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError(
                f"missing build tool {name}; install requirements/build.lock"
            ) from error
        if actual != version:
            raise ValueError(f"build tool {name} must be {version}, found {actual}")
    return expected


def command(arguments, *, cwd, env=None, capture=False):
    """Fixed caller-owned commands, no shell; build output goes to stderr."""
    # Trusted maintainer executable and arguments, never workflow values.
    result = subprocess.run(  # noqa: S603  # nosec B603
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        timeout=COMMAND_TIMEOUT,
        stdout=subprocess.PIPE if capture else sys.stderr,
        stderr=subprocess.PIPE if capture else sys.stderr,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip() if capture else None


def source_identity(git, root):
    status = command(
        [git, "status", "--porcelain", "--untracked-files=normal"], cwd=root, capture=True
    )
    if status:
        raise ValueError("release check requires a clean Git checkout, including untracked files")
    revision = command([git, "rev-parse", "HEAD"], cwd=root, capture=True)
    epoch = command([git, "show", "-s", "--format=%ct", revision], cwd=root, capture=True)
    if not re.fullmatch(r"[a-f0-9]{40,64}", revision) or not epoch.isdigit():
        raise ValueError("invalid Git revision or commit timestamp")
    return revision, epoch


def extract_source(archive, destination):
    """Extract only regular committed files/directories into a new private directory."""
    destination.mkdir()
    with tarfile.open(archive, "r:") as source:
        for member in source:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in member.name
                or ":" in member.name
                or not name.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("source archive contains an unsafe path or non-regular entry")
            target = destination.joinpath(*name.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("source archive entry escapes extraction directory")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            incoming = source.extractfile(member)
            if incoming is None:
                raise ValueError("source archive file has no data")
            with incoming, target.open("xb") as output:
                shutil.copyfileobj(incoming, output)
            target.chmod(0o644)
            os.utime(target, (member.mtime, member.mtime))


def artifacts(directory):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1 or len(list(directory.iterdir())) != 2:
        raise ValueError("build must produce exactly one wheel and one source distribution")
    return wheels[0], sources[0]


def compare_builds(first, second):
    wheel, sdist = artifacts(first)
    other_wheel, other_sdist = artifacts(second)
    if wheel.name != other_wheel.name or sha256(wheel) != sha256(other_wheel):
        raise ValueError("wheel bytes differ between independent builds; no candidate emitted")
    return wheel, sdist, sdist.name == other_sdist.name and sha256(sdist) == sha256(other_sdist)


def build_candidate(output_dir, *, root=ROOT):
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_relative_to(root):
        raise ValueError("output directory must be new and outside the source checkout")
    if not output_dir.parent.is_dir():
        raise ValueError("output directory parent must already exist")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is required for committed-source builds")
    revision, epoch = source_identity(git, root)
    lock = root / "requirements" / "build.lock"
    toolchain = check_toolchain(lock)
    lock_digest = sha256(lock)
    environment = {**os.environ, "SOURCE_DATE_EPOCH": epoch}
    command([sys.executable, "-I", "-m", "pip", "check"], cwd=root)
    with TemporaryDirectory(prefix="samsarix-release-") as temporary:
        work = Path(temporary)
        archive = work / "committed.tar"
        command([git, "archive", "--format=tar", "--output", str(archive), revision], cwd=root)
        for number in (1, 2):
            source = work / f"source{number}"
            extract_source(archive, source)
            if sha256(source / "requirements" / "build.lock") != lock_digest:
                raise ValueError("exported build lock differs from checked-out lock")
            command(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "build",
                    "--no-isolation",
                    "--outdir",
                    str(work / f"build{number}"),
                    str(source),
                ],
                cwd=work,
                env=environment,
            )
        wheel, sdist, sdist_identical = compare_builds(work / "build1", work / "build2")
        smoke = work / "smoke"
        command([sys.executable, "-I", "-m", "venv", str(smoke)], cwd=work)
        smoke_python = smoke / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command(
            [
                str(smoke_python),
                "-I",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            cwd=work,
        )
        command(
            [
                str(smoke_python),
                "-I",
                str(work / "source1" / "tests" / "installed_smoke.py"),
            ],
            cwd=work,
        )
        if source_identity(git, root) != (revision, epoch):
            raise ValueError("source checkout changed during release verification")
        report = {
            "release_check_version": 1,
            "source_revision": revision,
            "source_date_epoch": int(epoch),
            "build_lock_sha256": lock_digest,
            "toolchain": toolchain,
            "environment": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "system": platform.system(),
                "machine": platform.machine(),
                "zlib": zlib.ZLIB_RUNTIME_VERSION,
            },
            "checks": {
                "wheel_bytes_identical": True,
                "sdist_bytes_identical": sdist_identical,
                "installed_smoke": "passed",
            },
            "artifacts": [
                {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in (wheel, sdist)
            ],
        }
        output_dir.mkdir()
        for path in (wheel, sdist):
            with path.open("rb") as source, (output_dir / path.name).open("xb") as target:
                shutil.copyfileobj(source, target)
        with (output_dir / "SHA256SUMS").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "".join(f"{item['sha256']}  {item['name']}\n" for item in report["artifacts"])
            )
        with (output_dir / "release-check.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="new directory outside checkout"
    )
    args = parser.parse_args(argv)
    try:
        report = build_candidate(args.output_dir)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"release check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
