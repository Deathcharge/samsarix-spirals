# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Command-line interface for Samsarix Spirals."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .errors import WorkflowExecutionError, WorkflowValidationError
from .explain import explain_workflow
from .model import (
    DEFAULT_MAX_RUN_STEPS,
    MAX_DOCUMENT_BYTES,
    MAX_WORKFLOW_STEPS,
    JsonValue,
    load_json_object,
    load_workflow,
    parse_json_object_bytes,
)
from .runner import run_workflow
from .schema import SCHEMA_NAMES, get_schema
from .suite import load_suite, run_suite, suite_result_to_junit_xml

STARTER_WORKFLOW: dict[str, JsonValue] = {
    "schema_version": 1,
    "name": "hello",
    "description": "Validate a name and render a greeting.",
    "defaults": {"punctuation": "!"},
    "steps": [
        {
            "id": "require_name",
            "uses": "assert",
            "with": {
                "value": "{{ input.name }}",
                "operator": "not_empty",
                "message": "input.name is required",
            },
        },
        {
            "id": "greeting",
            "uses": "set",
            "with": {
                "message": "Hello, {{ input.name }}{{ defaults.punctuation }}",
                "name": "{{ input.name }}",
            },
        },
    ],
    "output": {
        "message": "{{ steps.greeting.message }}",
        "name": "{{ steps.greeting.name }}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samsarix-spirals",
        description="Validate, explain, and run deterministic local JSON workflows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a workflow without running it")
    validate.add_argument("workflow", type=Path)

    explain = commands.add_parser("explain", help="show workflow references without running it")
    explain.add_argument("workflow", type=Path)
    explain.add_argument("--compact", action="store_true", help="emit compact JSON")

    run = commands.add_parser("run", help="run a workflow")
    run.add_argument("workflow", type=Path)
    run.add_argument(
        "--input",
        type=str,
        metavar="PATH",
        help="JSON input object; use '-' to read standard input",
    )
    run.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_RUN_STEPS,
        choices=range(1, MAX_WORKFLOW_STEPS + 1),
        metavar=f"1..{MAX_WORKFLOW_STEPS}",
    )
    run.add_argument("--compact", action="store_true", help="emit compact JSON")
    run.add_argument(
        "--output-only",
        action="store_true",
        help="emit only the final JSON value, excluding the intermediate step trace",
    )

    test = commands.add_parser("test", help="run a workflow regression suite")
    test.add_argument("workflow", type=Path)
    test.add_argument("suite", type=Path)
    report = test.add_mutually_exclusive_group()
    report.add_argument("--json", action="store_true", help="emit a machine-readable report")
    report.add_argument("--junit", action="store_true", help="emit deterministic JUnit XML")
    test.add_argument("--compact", action="store_true", help="compact the JSON report")

    schema = commands.add_parser("schema", help="print a bundled JSON Schema")
    schema.add_argument("kind", choices=SCHEMA_NAMES)
    schema.add_argument("--compact", action="store_true", help="emit compact JSON")

    init = commands.add_parser("init", help="write a starter workflow without overwriting files")
    init.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            workflow = load_workflow(args.workflow)
            print(f"valid: {args.workflow} ({len(workflow.steps)} steps)")
            return 0
        if args.command == "explain":
            explanation = explain_workflow(load_workflow(args.workflow))
            indent = None if args.compact else 2
            print(
                json.dumps(explanation.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)
            )
            return 0
        if args.command == "init":
            return _init_workflow(args.path)
        if args.command == "schema":
            indent = None if args.compact else 2
            print(
                json.dumps(get_schema(args.kind), ensure_ascii=False, indent=indent, sort_keys=True)
            )
            return 0
        if args.command == "run":
            workflow = load_workflow(args.workflow)
            input_data = _load_input(args.input)
            run_result = run_workflow(workflow, input_data, max_steps=args.max_steps)
            indent = None if args.compact else 2
            payload = run_result.output if args.output_only else run_result.to_dict()
            print(json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True))
            return 0
        if args.command == "test":
            workflow = load_workflow(args.workflow)
            suite = load_suite(args.suite)
            suite_result = run_suite(workflow, suite)
            if args.junit:
                print(suite_result_to_junit_xml(suite_result, workflow=workflow.name))
            elif args.json:
                indent = None if args.compact else 2
                print(
                    json.dumps(
                        suite_result.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True
                    )
                )
            else:
                for case in suite_result.cases:
                    status = "PASS" if case.passed else "FAIL"
                    detail = f": {case.diagnostic}" if not case.passed else ""
                    print(f"{status} {case.name}{detail}")
                print(
                    f"suite {suite_result.suite}: "
                    f"{suite_result.passed} passed, {suite_result.failed} failed"
                )
            return 0 if suite_result.successful else 1
    except WorkflowExecutionError as error:
        print(f"execution error: {error}", file=sys.stderr)
        return 1
    except WorkflowValidationError as error:
        for issue in error.issues:
            print(f"validation error: {issue}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command!r}")


def _load_input(path: str | None) -> dict[str, JsonValue]:
    if path is None:
        return {}
    if path != "-":
        return load_json_object(path)
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    data = stream.read(MAX_DOCUMENT_BYTES + 1)
    if isinstance(data, str):
        data = data.encode("utf-8")
    return parse_json_object_bytes(data, source="<stdin>")


def _init_workflow(path: Path) -> int:
    content = json.dumps(STARTER_WORKFLOW, ensure_ascii=False, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise WorkflowValidationError(f"{path}: file already exists") from error
    except OSError as error:
        raise WorkflowValidationError(f"{path}: cannot create file: {error}") from error
    print(f"created: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
