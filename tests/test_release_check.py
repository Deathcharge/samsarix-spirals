# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Release evidence fails closed without invoking real builds in unit tests."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "release_check.py"
spec = importlib.util.spec_from_file_location("release_check", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def archive_file(path, entries):
    with tarfile.open(path, "w") as archive:
        for name, kind, payload in entries:
            entry = tarfile.TarInfo(name)
            entry.type = kind
            entry.mtime = 1_700_000_000
            entry.size = len(payload) if kind == tarfile.REGTYPE else 0
            archive.addfile(entry, io.BytesIO(payload) if kind == tarfile.REGTYPE else None)


def test_regular_source_extraction_preserves_bytes_and_timestamp(tmp_path):
    archive = tmp_path / "source.tar"
    archive_file(
        archive, [("src", tarfile.DIRTYPE, b""), ("src/a.py", tarfile.REGTYPE, b"value=1\n")]
    )
    destination = tmp_path / "source"
    release.extract_source(archive, destination)
    assert (destination / "src/a.py").read_bytes() == b"value=1\n"
    assert (destination / "src/a.py").stat().st_mtime == 1_700_000_000


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/escape", tarfile.REGTYPE),
        ("C:/escape", tarfile.REGTYPE),
        ("dir\\escape", tarfile.REGTYPE),
        ("link", tarfile.SYMTYPE),
        ("hardlink", tarfile.LNKTYPE),
        ("device", tarfile.CHRTYPE),
        ("pipe", tarfile.FIFOTYPE),
    ],
)
def test_source_extraction_rejects_paths_and_nonregular_entries(tmp_path, name, kind):
    archive = tmp_path / "source.tar"
    archive_file(archive, [(name, kind, b"data")])
    with pytest.raises(ValueError, match="unsafe path or non-regular"):
        release.extract_source(archive, tmp_path / "source")
    assert not (tmp_path / "escape").exists()


def test_extraction_cannot_overwrite_duplicate_entry(tmp_path):
    archive = tmp_path / "source.tar"
    archive_file(archive, [("a", tarfile.REGTYPE, b"first"), ("a", tarfile.REGTYPE, b"second")])
    with pytest.raises(FileExistsError):
        release.extract_source(archive, tmp_path / "source")
    assert (tmp_path / "source/a").read_bytes() == b"first"


@pytest.mark.parametrize("contents", ["", "build>=1", "build==1 --hash=md5:bad", "# only comment"])
def test_lock_rejects_missing_pins_hashes_and_empty_content(tmp_path, contents):
    lock = tmp_path / "build.lock"
    lock.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        release.locked_versions(lock)


def test_lock_requires_unique_pins_and_installed_versions(tmp_path, monkeypatch):
    lock = tmp_path / "build.lock"
    line = "build==1.5.0 --hash=sha256:" + "a" * 64 + "\n"
    lock.write_text(line + line, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        release.locked_versions(lock)
    lock.write_text(line, encoding="utf-8")
    monkeypatch.setattr(release.importlib.metadata, "version", lambda _: "1.5.0")
    assert release.check_toolchain(lock) == {"build": "1.5.0"}
    monkeypatch.setattr(release.importlib.metadata, "version", lambda _: "1.6.0")
    with pytest.raises(ValueError, match=r"must be 1\.5\.0"):
        release.check_toolchain(lock)

    def absent(_):
        raise release.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(release.importlib.metadata, "version", absent)
    with pytest.raises(ValueError, match="missing build tool"):
        release.check_toolchain(lock)


def test_clean_identity_is_bound_to_revision_and_commit_epoch(monkeypatch, tmp_path):
    values = iter(["", "a" * 40, "1700000000"])
    monkeypatch.setattr(release, "command", lambda *args, **kwargs: next(values))
    assert release.source_identity("git", tmp_path) == ("a" * 40, "1700000000")
    monkeypatch.setattr(release, "command", lambda *args, **kwargs: " M dirty.py")
    with pytest.raises(ValueError, match="clean Git checkout"):
        release.source_identity("git", tmp_path)
    values = iter(["", "not-a-revision", "1700000000"])
    monkeypatch.setattr(release, "command", lambda *args, **kwargs: next(values))
    with pytest.raises(ValueError, match="invalid Git revision"):
        release.source_identity("git", tmp_path)


def test_wheels_must_match_but_sdist_difference_is_reported(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    for directory in (one, two):
        directory.mkdir()
        (directory / "test.whl").write_bytes(b"wheel")
        (directory / "test.tar.gz").write_bytes(directory.name.encode())
    assert release.compare_builds(one, two) == (one / "test.whl", one / "test.tar.gz", False)
    (two / "test.whl").write_bytes(b"different")
    with pytest.raises(ValueError, match="wheel bytes differ"):
        release.compare_builds(one, two)
    (two / "other.whl").write_bytes(b"extra")
    with pytest.raises(ValueError, match="exactly one"):
        release.artifacts(two)


@pytest.mark.parametrize("destination", ["inside", "existing", "missing_parent"])
def test_output_safety_checked_before_build(tmp_path, destination):
    root = tmp_path / "repo"
    root.mkdir()
    output = {
        "inside": root / "out",
        "existing": tmp_path,
        "missing_parent": tmp_path / "missing/out",
    }[destination]
    with pytest.raises(ValueError, match="output directory"):
        release.build_candidate(output, root=root)


def test_build_command_has_timeout_no_shell_and_checked_status(monkeypatch, tmp_path):
    observed = {}

    def run(args, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(args, 0, " value\n", "")

    monkeypatch.setattr(release.subprocess, "run", run)
    assert release.command(["fixed", "arg"], cwd=tmp_path, capture=True) == "value"
    assert observed["check"] is True
    assert observed["timeout"] == 180 and "shell" not in observed


@pytest.mark.parametrize(
    "failure",
    [None, "changed_source", "failed_smoke", "changed_lock", "failed_build", "timeout", "wheel"],
)
def test_candidate_evidence_and_fail_closed_orchestration(tmp_path, monkeypatch, failure):
    root = tmp_path / "repo"
    (root / "requirements").mkdir(parents=True)
    lock = root / "requirements/build.lock"
    lock.write_text("build==1.5.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(release, "check_toolchain", lambda _: {"build": "1.5.0"})
    monkeypatch.setattr(release.shutil, "which", lambda _: "git")
    identities = iter(
        [
            ("a" * 40, "1700000000"),
            (("b" if failure == "changed_source" else "a") * 40, "1700000000"),
        ]
    )
    monkeypatch.setattr(release, "source_identity", lambda *args: next(identities))
    commands = []

    def command(args, *, cwd, env=None, capture=False):
        commands.append(args)
        if "archive" in args:
            archive_file(
                Path(args[args.index("--output") + 1]),
                [
                    (
                        "requirements/build.lock",
                        tarfile.REGTYPE,
                        b"changed" if failure == "changed_lock" else lock.read_bytes(),
                    )
                ],
            )
        if "build" in args:
            assert "--no-isolation" in args and "--skip-dependency-check" not in args
            assert env["SOURCE_DATE_EPOCH"] == "1700000000"
            if failure == "failed_build":
                raise subprocess.CalledProcessError(1, args)
            if failure == "timeout":
                raise subprocess.TimeoutExpired(args, 180)
            destination = Path(args[args.index("--outdir") + 1])
            destination.mkdir()
            wheel_bytes = destination.name.encode() if failure == "wheel" else b"wheel bytes"
            (destination / "package.whl").write_bytes(wheel_bytes)
            (destination / "package.tar.gz").write_bytes(destination.name.encode())
        if str(args[-1]).endswith("installed_smoke.py") and failure == "failed_smoke":
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(release, "command", command)
    output = tmp_path / "candidate"
    if failure:
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            release.build_candidate(output, root=root)
        assert not output.exists()
        return
    report = release.build_candidate(output, root=root)
    assert report == json.loads((output / "release-check.json").read_text(encoding="utf-8"))
    assert report["checks"] == {
        "wheel_bytes_identical": True,
        "sdist_bytes_identical": False,
        "installed_smoke": "passed",
    }
    assert report["source_revision"] == "a" * 40
    assert len(list(output.iterdir())) == 4
    assert str(tmp_path) not in json.dumps(report)
    for item in report["artifacts"]:
        assert item["sha256"] == release.sha256(output / item["name"])
        assert item["bytes"] == (output / item["name"]).stat().st_size
        assert f"{item['sha256']}  {item['name']}\n" in (output / "SHA256SUMS").read_text()
    install = next(args for args in commands if "install" in args)
    assert "--no-index" in install and "--no-deps" in install


def test_cli_failure_has_no_success_json(monkeypatch, capsys, tmp_path):
    def fail(_):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(release, "build_candidate", fail)
    assert release.main(["--output-dir", str(tmp_path / "out")]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "synthetic failure" in captured.err


def test_missing_git_emits_no_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(release.shutil, "which", lambda _: None)
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValueError, match="git is required"):
        release.build_candidate(tmp_path / "candidate", root=root)
    assert not (tmp_path / "candidate").exists()
