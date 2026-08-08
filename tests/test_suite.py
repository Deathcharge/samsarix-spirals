# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json

import pytest

from samsarix_spirals import (
    Workflow,
    WorkflowSuite,
    WorkflowValidationError,
    load_suite,
    run_suite,
)


def make_workflow() -> Workflow:
    return Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "contract",
            "steps": [
                {
                    "id": "required",
                    "uses": "assert",
                    "with": {
                        "value": "{{ input.name }}",
                        "operator": "not_empty",
                        "message": "name is required",
                    },
                },
                {"id": "shape", "uses": "set", "with": {"name": "{{ input.name }}"}},
            ],
            "output": "{{ steps.shape }}",
        }
    )


def make_suite() -> WorkflowSuite:
    return WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "contract cases",
            "cases": [
                {
                    "name": "shapes a name",
                    "input": {"name": "Ada"},
                    "expect": {"output": {"name": "Ada"}},
                },
                {
                    "name": "rejects an empty name",
                    "input": {"name": ""},
                    "expect": {
                        "error": {"step_id": "required", "message_contains": "name is required"}
                    },
                },
            ],
        }
    )


def test_runs_output_and_error_contracts() -> None:
    suite = make_suite()
    result = run_suite(make_workflow(), suite)

    assert result.successful
    assert result.passed == 2
    assert result.failed == 0
    assert result.to_dict() == {
        "suite": "contract cases",
        "successful": True,
        "passed": 2,
        "failed": 0,
        "cases": [
            {"name": "shapes a name", "passed": True},
            {"name": "rejects an empty name", "passed": True},
        ],
    }


def test_reports_expectation_mismatches_without_disclosing_values() -> None:
    workflow = make_workflow()
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "mismatches",
            "cases": [
                {"name": "wrong output", "input": {"name": "Ada"}, "expect": {"output": {}}},
                {
                    "name": "unexpected error",
                    "input": {"name": ""},
                    "expect": {"output": {"name": ""}},
                },
                {
                    "name": "expected error",
                    "input": {"name": "Ada"},
                    "expect": {"error": {}},
                },
                {
                    "name": "wrong step",
                    "input": {"name": ""},
                    "expect": {"error": {"step_id": "other"}},
                },
                {
                    "name": "wrong message",
                    "input": {"name": ""},
                    "expect": {"error": {"message_contains": "different"}},
                },
            ],
        }
    )

    result = run_suite(workflow, suite)

    assert result.failed == 5
    assert not result.successful
    details = [case.detail for case in result.cases]
    assert details == [
        "workflow output did not equal expected output",
        "workflow failed but output was expected",
        "workflow completed but an execution error was expected",
        "execution failed at an unexpected step",
        "execution error did not contain expected text",
    ]
    assert "Ada" not in json.dumps(result.to_dict())


@pytest.mark.parametrize(
    "document,message",
    [
        ({}, "suite_version"),
        ({"suite_version": True, "name": "x", "cases": []}, "integer 1"),
        ({"suite_version": 1, "name": "", "cases": []}, "non-empty string"),
        ({"suite_version": 1, "name": "x", "cases": "no"}, "must be an array"),
        (
            {
                "suite_version": 1,
                "name": "x",
                "cases": [{"name": "one", "expect": {"output": 1, "error": {}}}],
            },
            "exactly one",
        ),
        (
            {
                "suite_version": 1,
                "name": "x",
                "cases": [
                    {"name": "same", "expect": {"output": 1}},
                    {"name": "same", "expect": {"output": 1}},
                ],
            },
            "duplicates case name",
        ),
        (
            {
                "suite_version": 1,
                "name": "x",
                "cases": [{"name": "one", "input": [], "expect": {"output": 1}}],
            },
            "input must be an object",
        ),
        (
            {
                "suite_version": 1,
                "name": "x",
                "cases": [{"name": "one", "expect": {"error": "bad"}}],
            },
            "error must be an object",
        ),
        (
            {
                "suite_version": 1,
                "name": "x",
                "cases": [
                    {
                        "name": "one",
                        "expect": {"error": {"step_id": "", "message_contains": ""}},
                    }
                ],
            },
            "non-empty string",
        ),
    ],
)
def test_rejects_invalid_suites(document: dict[str, object], message: str) -> None:
    with pytest.raises(WorkflowValidationError, match=message):
        WorkflowSuite.from_dict(document)


def test_load_suite_adds_source_path(tmp_path) -> None:
    path = tmp_path / "invalid.suite.json"
    path.write_text('{"suite_version":1,"name":"bad","cases":[]}', encoding="utf-8")

    with pytest.raises(WorkflowValidationError, match=r"invalid\.suite\.json"):
        load_suite(path)
