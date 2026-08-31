# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Useful suite failure locations without leaking payloads or exception messages."""

from __future__ import annotations

import json
from xml.etree import ElementTree

import pytest

from samsarix_spirals import Workflow, WorkflowSuite, run_suite, suite_result_to_junit_xml
from samsarix_spirals.ci import main as ci_main
from samsarix_spirals.cli import main as cli_main
from samsarix_spirals.suite import CaseResult, SuiteResult

PRIVATE_MARKER = "private-fixture-or-message-must-not-appear"


def documents():
    workflow = {
        "schema_version": 1,
        "name": "approval-contract",
        "steps": [
            {
                "id": "require_approval",
                "uses": "assert",
                "with": {
                    "value": "{{ input.approved }}",
                    "operator": "equals",
                    "expected": True,
                    "message": PRIVATE_MARKER,
                },
            },
            {"id": "out", "uses": "set", "with": {"value": "{{ input.value }}"}},
        ],
    }
    suite = {
        "suite_version": 1,
        "name": "diagnostics",
        "cases": [
            {"name": "unexpected error", "input": {"approved": False}, "expect": {"output": {}}},
            {
                "name": "wrong step",
                "input": {"approved": False},
                "expect": {"error": {"step_id": PRIVATE_MARKER}},
            },
            {
                "name": "wrong message",
                "input": {"approved": False},
                "expect": {"error": {"message_contains": "another-private-message"}},
            },
            {
                "name": "missing error",
                "input": {"approved": True, "value": PRIVATE_MARKER},
                "expect": {"error": {}},
            },
            {
                "name": "wrong output",
                "input": {"approved": True, "value": PRIVATE_MARKER},
                "expect": {"output": {"secret": PRIVATE_MARKER}},
            },
            {
                "name": "expected failure",
                "input": {"approved": False},
                "expect": {
                    "error": {"step_id": "require_approval", "message_contains": PRIVATE_MARKER}
                },
            },
            {
                "name": "expected success",
                "input": {"approved": True, "value": PRIVATE_MARKER},
                "expect": {"output": {"value": PRIVATE_MARKER}},
            },
        ],
    }
    return workflow, suite


def test_failure_codes_and_actual_steps_preserve_existing_details_and_pass_shape():
    workflow, suite = documents()
    result = run_suite(Workflow.from_dict(workflow), WorkflowSuite.from_dict(suite))
    assert [case.failure_code for case in result.cases] == [
        "unexpected_execution_error",
        "unexpected_step",
        "error_message_mismatch",
        "expected_execution_error",
        "output_mismatch",
        None,
        None,
    ]
    assert [case.step_id for case in result.cases] == ["require_approval"] * 3 + [None] * 4
    assert result.failed == 5 and result.passed == 2
    for case in result.to_dict()["cases"][:3]:
        assert case["step_id"] == "require_approval"
        assert (
            "step" not in case["detail"]
            or case["detail"] == "execution failed at an unexpected step"
        )
    for case in result.to_dict()["cases"][3:]:
        assert "step_id" not in case
    assert result.to_dict()["cases"][-1] == {"name": "expected success", "passed": True}
    assert result.cases[-1].diagnostic == ""
    serialized = json.dumps(result.to_dict())
    assert PRIVATE_MARKER not in serialized and "another-private-message" not in serialized


@pytest.mark.parametrize("boundary", ["final", "step_limit"])
@pytest.mark.parametrize(
    "expect,code",
    [
        ({"output": {}}, "unexpected_execution_error"),
        ({"error": {"step_id": "out"}}, "unexpected_step"),
        ({"error": {"message_contains": "private-never-matching"}}, "error_message_mismatch"),
    ],
)
def test_errors_without_step_never_invent_last_or_expected_step(boundary, expect, code):
    workflow, suite = documents()
    if boundary == "final":
        workflow["output"] = "{{ input.absent }}"
    else:
        workflow["steps"] = [{"id": f"s{i}", "uses": "set", "with": {}} for i in range(101)]
    suite["cases"] = [
        {
            "name": "boundary",
            "input": {"approved": True, "value": PRIVATE_MARKER},
            "expect": expect,
        }
    ]
    case = run_suite(Workflow.from_dict(workflow), WorkflowSuite.from_dict(suite)).cases[0]
    assert case.failure_code == code
    assert case.step_id is None
    assert "step_id" not in case.to_dict()
    assert case.diagnostic == case.detail


@pytest.mark.parametrize(
    "uses,body",
    [
        ("map", {"template": "{{ item.absent }}"}),
        ("filter", {"where": {"value": "{{ item.absent }}", "operator": "truthy"}}),
    ],
)
def test_collection_error_reports_outer_step_not_private_item_or_path(uses, body):
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "collection",
            "steps": [
                {"id": "batch", "uses": uses, "with": {"items": "{{ input.rows }}", **body}},
            ],
        }
    )
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "collection",
            "cases": [
                {
                    "name": "batch error",
                    "input": {"rows": [{"secret": PRIVATE_MARKER}]},
                    "expect": {"output": []},
                },
            ],
        }
    )
    case = run_suite(workflow, suite).cases[0]
    assert case.step_id == "batch"
    assert case.failure_code == "unexpected_execution_error"
    assert "item[" not in case.diagnostic and "absent" not in case.diagnostic
    assert PRIVATE_MARKER not in json.dumps(case.to_dict())


@pytest.mark.parametrize("mode", ["human", "json", "junit", "ci", "annotations"])
def test_all_report_consumers_expose_step_but_no_private_values(tmp_path, capsys, mode):
    workflow, suite = documents()
    paths = [tmp_path / "workflow.json", tmp_path / "suite.json"]
    for path, document in zip(paths, [workflow, suite], strict=True):
        path.write_text(json.dumps(document), encoding="utf-8")
    args = [str(path) for path in paths]
    if mode in {"ci", "annotations"}:
        status = ci_main((["--github-annotations"] if mode == "annotations" else []) + args)
    else:
        status = cli_main(["test", *args, *([f"--{mode}"] if mode != "human" else [])])
    captured = capsys.readouterr()
    assert status == 1 and captured.err == ""
    assert "require_approval" in captured.out
    assert PRIVATE_MARKER not in captured.out and "another-private-message" not in captured.out
    if mode in {"json", "ci", "annotations"}:
        report = json.loads(captured.out.splitlines()[0] if mode != "json" else captured.out)
        assert report["cases"][0]["failure_code"] == "unexpected_execution_error"
        assert report["cases"][0]["step_id"] == "require_approval"
    if mode == "annotations":
        annotations = captured.out.splitlines()[1:]
        assert len(annotations) == 5
        assert 'step "require_approval"' in annotations[0]
        assert "file=" not in annotations[0] and "line=" not in annotations[0]
    if mode == "junit":
        root = ElementTree.fromstring(captured.out)  # noqa: S314 - locally generated report
        failures = root.findall("testcase/failure")
        assert len(failures) == 5
        assert failures[0].text.endswith('[step "require_approval"]')
        assert failures[0].attrib["message"] == failures[0].text
        assert failures[0].attrib["type"] == "SamsarixContractFailure"


def test_diagnostic_quotes_control_characters_even_in_directly_constructed_records():
    case = CaseResult("case", False, "generic mismatch", "unexpected_step", 'bad\n\r%0A\x1b<&"')
    assert (
        "\n" not in case.diagnostic
        and "\r" not in case.diagnostic
        and "\x1b" not in case.diagnostic
    )
    report = suite_result_to_junit_xml(SuiteResult("suite", (case,)), workflow="workflow")
    root = ElementTree.fromstring(report)  # noqa: S314 - locally generated report
    assert root.find("testcase/failure").text == case.diagnostic


def test_legacy_case_result_construction_is_compatible():
    case = CaseResult("legacy", False, "generic failure")
    assert case.to_dict() == {"name": "legacy", "passed": False, "detail": "generic failure"}
    assert case.diagnostic == "generic failure"
    assert CaseResult("legacy", False).diagnostic == "workflow contract failed"
