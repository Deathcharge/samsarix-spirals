# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Keep documented consumer pins and copy-paste evaluation fixtures executable."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

from samsarix_spirals.cli import main

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "integration_smoke", ROOT / "tests/integration_smoke.py"
)
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


def test_documented_pins_match_public_action_ci_and_evaluation_checkout():
    guide = (ROOT / "docs/REPOSITORY_INTEGRATIONS.md").read_text(encoding="utf-8")
    revision = integration.documented_revision(guide)
    public_action = r"Deathcharge/samsarix-spirals@([a-f0-9]{40})\b"
    assert re.findall(public_action, guide) == [revision]
    ci = (ROOT / ".github/workflows/consumer.yml").read_text(encoding="utf-8")
    assert re.findall(public_action, ci) == [revision]
    assert "python tests/integration_smoke.py --documented-pin" in ci
    assert "fetch-depth: 0" in ci
    evaluation = (ROOT / "docs/EVALUATION.md").read_text(encoding="utf-8")
    assert re.findall(r"git checkout --detach ([a-f0-9]{40})\b", evaluation) == [revision]


@pytest.mark.parametrize(
    "text",
    ["", "    rev: master", "    rev: abc123", "    rev: " + "A" * 40, "    rev: " + "a" * 41],
)
def test_guide_revision_requires_a_full_lowercase_commit(text):
    with pytest.raises(ValueError, match="exactly one full"):
        integration.documented_revision(text)


def test_guide_revision_rejects_duplicate_pin_blocks():
    line = "    rev: " + "a" * 40 + "\n"
    assert integration.documented_revision(line) == "a" * 40
    with pytest.raises(ValueError, match="exactly one full"):
        integration.documented_revision(line * 2)


def test_missing_documented_commit_stops_before_installing_a_hook(monkeypatch):
    monkeypatch.setattr(integration.shutil, "which", lambda _: "git")
    commands = []

    def command(args, cwd, env):
        commands.append(args)
        return subprocess.CompletedProcess(args, int("cat-file" in args), "a" * 40, "")

    monkeypatch.setattr(integration, "command", command)
    with pytest.raises(RuntimeError, match="fetch repository history"):
        integration.main(["--documented-pin"])
    assert len(commands) == 2 and commands[-1][1:3] == ["cat-file", "-e"]


def test_evaluation_json_examples_match_documented_cli_failure_and_recovery(tmp_path, capsys):
    guide = (ROOT / "docs/EVALUATION.md").read_text(encoding="utf-8")
    snippets = [json.loads(text) for text in re.findall(r"```json\n(.*?)\n```", guide, re.DOTALL)]
    assert len(snippets) == 2
    workflow = str(ROOT / "examples/release-targets.json")
    suite_path = tmp_path / "evaluation.suite.local.json"
    for snippet, code, step in zip(
        snippets, ["output_mismatch", "unexpected_execution_error"], [None, "names"], strict=True
    ):
        suite_path.write_text(json.dumps(snippet), encoding="utf-8")
        assert main(["test", workflow, str(suite_path), "--json", "--compact"]) == 1
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["successful"] is False and result["failed"] == 1
        assert result["cases"][0]["failure_code"] == code
        if step is None:
            assert "step_id" not in result["cases"][0]
        else:
            assert result["cases"][0]["step_id"] == step
        assert "template reference" not in captured.out and "LINUX-X64" not in captured.out
        assert captured.err == ""
    snippets[0]["cases"][0]["expect"]["output"] = ["linux-x64"]
    suite_path.write_text(json.dumps(snippets[0]), encoding="utf-8")
    assert main(["test", workflow, str(suite_path), "--json", "--compact"]) == 0
    assert json.loads(capsys.readouterr().out)["successful"] is True
    suite_path.write_text("not json", encoding="utf-8")
    assert main(["test", workflow, str(suite_path), "--json", "--compact"]) == 2
