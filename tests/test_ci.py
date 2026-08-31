# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from samsarix_spirals.ci import _annotation, main

ROOT = Path(__file__).resolve().parents[1]


def fixtures(tmp_path, *, failed=False, cases=1, name="contract"):
    workflow = tmp_path / "workflow ; literal.json"
    suite = tmp_path / "suite with spaces.json"
    workflow.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "identity",
                "steps": [{"id": "out", "uses": "set", "with": {"secret": "{{ input.secret }}"}}],
            }
        ),
        encoding="utf-8",
    )
    suite.write_text(
        json.dumps(
            {
                "suite_version": 1,
                "name": name,
                "cases": [
                    {
                        "name": f"{name}{i}",
                        "input": {"secret": "fixture-must-not-leak"},
                        "expect": {"output": {} if failed else {"secret": "fixture-must-not-leak"}},
                    }
                    for i in range(cases)
                ],
            }
        ),
        encoding="utf-8",
    )
    return workflow, suite


@pytest.mark.parametrize("failed", [False, True])
def test_ci_reports_exit_status_and_never_fixture_values(tmp_path, capsys, failed):
    workflow, suite = fixtures(tmp_path, failed=failed)
    assert main([str(workflow), str(suite)]) == int(failed)
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 1
    assert "fixture-must-not-leak" not in captured.out
    assert json.loads(captured.out)["successful"] is not failed
    assert captured.err == ""


def test_github_annotations_are_bounded_and_escape_untrusted_names(tmp_path, capsys):
    name = "line\n::add-mask::not-a-command\r%0A\x1b"
    workflow, suite = fixtures(tmp_path, failed=True, cases=12, name=name)
    assert main(["--github-annotations", str(workflow), str(suite)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 12  # One report, ten case annotations, one overflow summary.
    assert json.loads(lines[0])["failed"] == 12
    assert all(line.startswith("::error title=Samsarix contract::") for line in lines[1:])
    assert "%250A" in lines[1]
    assert "2 additional failures" in lines[-1]
    assert "\x1b" not in "".join(lines)


def test_annotation_escapes_each_command_delimiter(capsys):
    _annotation("a%\r\n::warning::b")
    assert capsys.readouterr().out == "::error title=Samsarix contract::a%25%0D%0A::warning::b\n"


@pytest.mark.parametrize("annotations", [False, True])
def test_invalid_documents_return_two_with_single_line_diagnostics(tmp_path, capsys, annotations):
    workflow, suite = fixtures(tmp_path)
    workflow.write_text('{"bad\\n::warning::injected": 1}', encoding="utf-8")
    args = [str(workflow), str(suite)]
    if annotations:
        args.insert(0, "--github-annotations")
    assert main(args) == 2
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 + int(annotations)
    assert json.loads(lines[0])["status"] == "invalid"


def test_bootstrap_ignores_consumer_imports_pythonpath_and_shell_metacharacters(tmp_path):
    workflow, suite = fixtures(tmp_path)
    (tmp_path / "samsarix_spirals.py").write_text(
        "raise RuntimeError('shadow imported')", encoding="utf-8"
    )
    (tmp_path / "json.py").write_text(
        "raise RuntimeError('json shadow imported')", encoding="utf-8"
    )
    env = {
        **os.environ,
        "GITHUB_WORKSPACE": str(tmp_path),
        "PYTHONPATH": str(tmp_path),
        "SAMSARIX_WORKFLOW": str(workflow),
        "SAMSARIX_SUITE": str(suite),
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(ROOT / "integrations" / "run_action.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["successful"]
    assert not (tmp_path / "literal.json").exists()


def test_bootstrap_missing_inputs_fails_closed(tmp_path):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"SAMSARIX_WORKFLOW", "SAMSARIX_SUITE"}
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(ROOT / "integrations" / "run_action.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout.splitlines()[0])["status"] == "invalid"


@pytest.mark.parametrize("filename", ["../outside.json", "", "missing.json"])
def test_action_workspace_restriction_rejects_escape_directory_and_missing(
    tmp_path, capsys, filename
):
    root = tmp_path / "workspace"
    root.mkdir()
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    _workflow, suite = fixtures(root)
    assert main(["--workspace", str(root), "--", filename, str(suite)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"


def test_workspace_restriction_rejects_absolute_outside_path(tmp_path, capsys):
    workflow, suite = fixtures(tmp_path)
    root = tmp_path / "workspace"
    root.mkdir()
    assert main(["--workspace", str(root), str(workflow), str(suite)]) == 2
    assert "regular file inside the workspace" in capsys.readouterr().out


def test_workspace_restriction_follows_symlinks_before_accepting(tmp_path, capsys):
    outside, suite = fixtures(tmp_path)
    root = tmp_path / "workspace"
    root.mkdir()
    link = root / "linked.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("creating a symlink requires platform support/permission")
    assert main(["--workspace", str(root), str(link), str(suite)]) == 2
    assert "regular file inside the workspace" in capsys.readouterr().out
