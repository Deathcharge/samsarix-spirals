# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Run with a wheel-only venv Python to verify real installed CLI boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def invoke(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    # Fixed Python executable/module; no shell or executable supplied by fixtures.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-m", "samsarix_spirals", *arguments],
        input=input_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )


def main() -> None:
    workflow = str(EXAMPLES / "agent-tool-result.json")
    fixture = json.loads((EXAMPLES / "agent-tool-result.input.json").read_text(encoding="utf-8"))
    result = invoke(
        "run",
        workflow,
        "--input",
        "-",
        "--output-only",
        "--compact",
        input_text=json.dumps(fixture),
    )
    expected = {
        "ticket_id": "INC-42",
        "summary": "Investigate latency regression",
        "priority": "high",
        "source": "agent",
        "reviewed": True,
    }
    if result.returncode != 0 or result.stderr:
        raise RuntimeError("Installed CLI failed the approved output-only fixture")
    if json.dumps(json.loads(result.stdout), sort_keys=True) != json.dumps(
        expected, sort_keys=True
    ):
        raise RuntimeError("Installed CLI output contract mismatch")

    fixture["approved"] = 1
    rejected = invoke(
        "run", workflow, "--input", "-", "--output-only", input_text=json.dumps(fixture)
    )
    if rejected.returncode != 1 or rejected.stdout or "requires approval" not in rejected.stderr:
        raise RuntimeError("Installed CLI did not reject numeric approval without partial stdout")

    suite_paths = sorted(EXAMPLES.glob("*.suite.json"))
    if not suite_paths:
        raise RuntimeError("No example suites found in the distribution checkout")
    for suite_path in suite_paths:
        workflow_path = suite_path.with_name(suite_path.name.removesuffix(".suite.json") + ".json")
        report = invoke("test", str(workflow_path), str(suite_path), "--json", "--compact")
        if report.returncode != 0 or report.stderr or not json.loads(report.stdout)["successful"]:
            raise RuntimeError(f"Installed CLI suite failed: {suite_path.name}")
    print(f"Installed CLI boundaries and {len(suite_paths)} example suites passed")


if __name__ == "__main__":
    main()
