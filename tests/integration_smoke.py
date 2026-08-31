# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Exercise the real pre-commit consumer lifecycle against a committed revision."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def command(
    arguments: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        arguments,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
        check=False,
    )


def documented_revision(text: str) -> str:
    revisions = re.findall(r"^\s+rev: ([a-f0-9]{40})\s*$", text, re.MULTILINE)
    if len(revisions) != 1:
        raise ValueError("integration guide must contain exactly one full pre-commit revision")
    return revisions[0]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--documented-pin", action="store_true", help="test the guide's exact pre-commit revision"
    )
    args = parser.parse_args(argv)
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for the pre-commit consumer test")
    revision = command([git, "rev-parse", "HEAD"], ROOT, dict(os.environ))
    if revision.returncode:
        raise RuntimeError(revision.stderr)
    selected_revision = revision.stdout.strip()
    if args.documented_pin:
        selected_revision = documented_revision(
            (ROOT / "docs" / "REPOSITORY_INTEGRATIONS.md").read_text(encoding="utf-8")
        )
        available = command(
            [git, "cat-file", "-e", selected_revision + "^{commit}"], ROOT, dict(os.environ)
        )
        if available.returncode:
            raise RuntimeError("documented commit is missing locally; fetch repository history")
    with TemporaryDirectory(prefix="samsarix-consumer-") as directory:
        consumer = Path(directory) / "consumer with spaces"
        consumer.mkdir()
        env = {**os.environ, "PRE_COMMIT_HOME": str(Path(directory) / "hook-cache")}
        initialized = command([git, "init", "--quiet"], consumer, env)
        if initialized.returncode:
            raise RuntimeError(initialized.stderr)
        for source, target in [
            ("release-targets.json", "workflow with spaces.json"),
            ("release-targets.suite.json", "suite with spaces.json"),
        ]:
            shutil.copyfile(ROOT / "examples" / source, consumer / target)
        # JSON is valid YAML, avoiding a test-only YAML serialization dependency.
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        config = {
            "repos": [
                {
                    "repo": ROOT.as_uri(),
                    "rev": selected_revision,
                    "hooks": [
                        {
                            "id": "samsarix-spirals-test",
                            "language_version": python_version,
                            "args": ["workflow with spaces.json", "suite with spaces.json"],
                        }
                    ],
                }
            ]
        }
        (consumer / ".pre-commit-config.yaml").write_text(json.dumps(config), encoding="utf-8")
        staged = command([git, "add", "--", "."], consumer, env)
        if staged.returncode:
            raise RuntimeError(staged.stderr)
        invocation = [sys.executable, "-m", "pre_commit", "run", "--all-files", "--verbose"]
        passed = command(invocation, consumer, env)
        if passed.returncode or '"successful": true' not in passed.stdout:
            raise RuntimeError(f"Fresh hook failed:\n{passed.stdout}\n{passed.stderr}")
        suite_path = consumer / "suite with spaces.json"
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["cases"][0]["expect"] = {"output": ["deliberately-wrong"]}
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        failed = command(invocation, consumer, env)
        if failed.returncode != 1 or '"successful": false' not in failed.stdout:
            raise RuntimeError(
                f"Incorrect hook failure contract:\n{failed.stdout}\n{failed.stderr}"
            )
        if '"failure_code": "output_mismatch"' not in failed.stdout:
            raise RuntimeError("Installed hook omitted the output-mismatch failure code")
        suite["cases"][0]["input"] = {"targets": [{"enabled": True}]}
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        execution_failed = command(invocation, consumer, env)
        if (
            execution_failed.returncode != 1
            or '"failure_code": "unexpected_execution_error"' not in execution_failed.stdout
            or '"step_id": "names"' not in execution_failed.stdout
            or "template reference" in execution_failed.stdout
        ):
            raise RuntimeError("Installed hook failure location/privacy contract failed")
        suite_path.write_text("not json", encoding="utf-8")
        invalid = command(invocation, consumer, env)
        if invalid.returncode != 1 or '"status": "invalid"' not in invalid.stdout:
            raise RuntimeError(
                f"Invalid document was not rejected:\n{invalid.stdout}\n{invalid.stderr}"
            )
    print(
        f"Fresh consumer hook {selected_revision}: install, pass, mismatch, "
        "step diagnostics, and invalid-document cases passed"
    )


if __name__ == "__main__":
    main()
