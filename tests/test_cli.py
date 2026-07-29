# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import io
import json
import sys

import pytest

from samsarix_spirals.cli import main


def write_workflow(path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "cli-test",
                "steps": [
                    {
                        "id": "hello",
                        "uses": "set",
                        "with": {"message": "Hello {{ input.name }}"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_validate_and_run_commands(tmp_path, capsys) -> None:
    workflow = tmp_path / "workflow.json"
    input_path = tmp_path / "input.json"
    write_workflow(workflow)
    input_path.write_text('{"name":"Ada"}', encoding="utf-8")

    assert main(["validate", str(workflow)]) == 0
    assert "valid:" in capsys.readouterr().out

    assert main(["run", str(workflow), "--input", str(input_path), "--compact"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["output"] == {"message": "Hello Ada"}
    assert captured.err == ""


def test_run_reads_standard_input(tmp_path, capsys, monkeypatch) -> None:
    workflow = tmp_path / "workflow.json"
    write_workflow(workflow)
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"name":"Grace"}'))

    assert main(["run", str(workflow), "--input", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["output"]["message"] == "Hello Grace"


def test_init_does_not_overwrite(tmp_path, capsys) -> None:
    path = tmp_path / "starter.json"

    assert main(["init", str(path)]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert "created:" in capsys.readouterr().out

    assert main(["init", str(path)]) == 2
    assert "already exists" in capsys.readouterr().err

    assert main(["init", str(tmp_path / "missing" / "starter.json")]) == 2
    assert "cannot create file" in capsys.readouterr().err


def test_validation_and_execution_errors_use_distinct_exit_codes(tmp_path, capsys) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    assert main(["validate", str(invalid)]) == 2
    assert "validation error:" in capsys.readouterr().err

    failing = tmp_path / "failing.json"
    failing.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "failure",
                "steps": [
                    {
                        "id": "check",
                        "uses": "assert",
                        "with": {"value": False, "operator": "truthy"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert main(["run", str(failing)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "execution error:" in captured.err


def test_version_and_required_command(capsys) -> None:
    with pytest.raises(SystemExit) as version:
        main(["--version"])
    assert version.value.code == 0
    assert "0.1.0" in capsys.readouterr().out

    with pytest.raises(SystemExit) as missing:
        main([])
    assert missing.value.code == 2
