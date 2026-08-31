# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Value-redacted, single-line reports for CI and pre-commit consumers."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .errors import WorkflowValidationError
from .model import load_workflow
from .suite import load_suite, run_suite


def _annotation(message: str) -> None:
    # GitHub decodes percent escapes after identifying a single workflow command.
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Samsarix contract::{escaped}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one contract suite without echoing input/output fixture values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-annotations", action="store_true")
    parser.add_argument("--workspace", type=Path, help="restrict documents to this directory")
    parser.add_argument("workflow")
    parser.add_argument("suite")
    args = parser.parse_args(argv)
    try:
        workflow_path, suite_path = Path(args.workflow), Path(args.suite)
        if args.workspace is not None:
            workflow_path = _workspace_file(args.workflow, args.workspace)
            suite_path = _workspace_file(args.suite, args.workspace)
        result = run_suite(load_workflow(workflow_path), load_suite(suite_path))
    except WorkflowValidationError as error:
        # JSON escaping prevents multiline labels/paths from becoming runner commands
        # or terminal control sequences. Detailed diagnostics stay in this one line.
        print(json.dumps({"status": "invalid", "issues": error.issues}, ensure_ascii=True))
        if args.github_annotations:
            _annotation("Invalid workflow or suite; see the JSON diagnostics.")
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=True, sort_keys=True))
    if args.github_annotations:
        for case in [case for case in result.cases if not case.passed][:10]:
            # Quoting names also escapes terminal controls and lone Unicode surrogates.
            _annotation(f"Case {json.dumps(case.name, ensure_ascii=True)}: {case.diagnostic}")
        if result.failed > 10:
            _annotation(f"{result.failed - 10} additional failures; see the JSON report.")
    return 0 if result.successful else 1


def _workspace_file(value: str, workspace: Path) -> Path:
    try:
        root = workspace.resolve(strict=True)
        path = (root / value).resolve(strict=True)
        if not value or not path.is_relative_to(root) or not path.is_file():
            raise WorkflowValidationError("document must be a regular file inside the workspace")
        return path
    except (OSError, RuntimeError, ValueError) as error:
        raise WorkflowValidationError(
            "document must be a regular file inside the workspace"
        ) from error


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
