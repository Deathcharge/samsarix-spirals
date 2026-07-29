# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json

import pytest

from samsarix_spirals import Workflow, WorkflowValidationError, load_workflow
from samsarix_spirals.errors import WorkflowValidationError as DirectValidationError
from samsarix_spirals.model import (
    MAX_DOCUMENT_BYTES,
    MAX_WORKFLOW_STEPS,
    parse_json_object_bytes,
    parse_workflow_bytes,
)


def workflow_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "test",
        "description": "A test workflow",
        "defaults": {"suffix": "!"},
        "steps": [
            {
                "id": "first",
                "uses": "set",
                "with": {"message": "Hi {{ input.name }}{{ defaults.suffix }}"},
            },
            {
                "id": "second",
                "uses": "assert",
                "with": {
                    "value": "{{ steps.first.message }}",
                    "operator": "not_empty",
                },
            },
        ],
        "output": "{{ steps.first }}",
    }


def test_workflow_round_trip() -> None:
    document = workflow_document()
    workflow = Workflow.from_dict(document)

    assert workflow.name == "test"
    assert workflow.description == "A test workflow"
    assert [step.id for step in workflow.steps] == ["first", "second"]
    assert workflow.to_dict() == document

    document["name"] = "mutated"
    assert workflow.name == "test"


def test_load_workflow_from_file(tmp_path) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(workflow_document()), encoding="utf-8")

    assert load_workflow(path).name == "test"


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"schema_version": 2}, "schema_version"),
        ({"name": ""}, "name"),
        ({"name": "x" * 101}, "100 characters"),
        ({"description": 3}, "description"),
        ({"description": "x" * 501}, "500 characters"),
        ({"defaults": []}, "defaults"),
        ({"steps": []}, "at least one"),
        ({"extra": True}, "unknown field"),
    ],
)
def test_rejects_invalid_top_level_fields(change: dict[str, object], expected: str) -> None:
    document = workflow_document()
    document.update(change)

    with pytest.raises(WorkflowValidationError, match=expected):
        Workflow.from_dict(document)


@pytest.mark.parametrize(
    "step, expected",
    [
        (None, "must be an object"),
        ({"id": "1bad", "uses": "set", "with": {}}, "must match"),
        ({"id": "good", "uses": "http", "with": {}}, "must be one of"),
        ({"id": "good", "uses": "set", "with": [], "extra": 1}, "unknown field"),
        ({"id": "good", "uses": "assert", "with": {}}, "value is required"),
        (
            {"id": "good", "uses": "assert", "with": {"value": 1, "operator": "equals"}},
            "expected is required",
        ),
        (
            {"id": "good", "uses": "assert", "with": {"value": 1, "operator": "bad"}},
            "operator must be one of",
        ),
        (
            {
                "id": "good",
                "uses": "assert",
                "with": {"value": 1, "operator": "truthy", "message": 3},
            },
            "message must be a string",
        ),
    ],
)
def test_rejects_invalid_steps(step: object, expected: str) -> None:
    document = workflow_document()
    document["steps"] = [step]

    with pytest.raises(WorkflowValidationError, match=expected):
        Workflow.from_dict(document)


def test_rejects_duplicate_step_ids() -> None:
    document = workflow_document()
    document["steps"] = [
        {"id": "same", "uses": "set", "with": {}},
        {"id": "same", "uses": "set", "with": {}},
    ]

    with pytest.raises(WorkflowValidationError, match="duplicates step id"):
        Workflow.from_dict(document)


@pytest.mark.parametrize(
    "template, expected",
    [
        ("{{ secret.value }}", "unsupported template root"),
        ("{{ steps }}", "must name a step"),
        ("{{ steps.later.value }}", "before it is available"),
        ("{{ defaults.missing }}", "missing default"),
        ("{{ input.name", "malformed template syntax"),
    ],
)
def test_rejects_invalid_templates(template: str, expected: str) -> None:
    document = workflow_document()
    document["steps"] = [
        {"id": "first", "uses": "set", "with": {"value": template}},
        {"id": "later", "uses": "set", "with": {}},
    ]

    with pytest.raises(WorkflowValidationError, match=expected):
        Workflow.from_dict(document)


def test_rejects_duplicate_json_keys_and_non_finite_numbers() -> None:
    with pytest.raises(WorkflowValidationError, match="duplicate object key"):
        parse_workflow_bytes(b'{"schema_version":1,"name":"a","name":"b","steps":[]}')

    with pytest.raises(WorkflowValidationError, match="non-finite"):
        parse_json_object_bytes(b'{"value":NaN}')


def test_rejects_large_invalid_or_non_object_documents(tmp_path) -> None:
    large = tmp_path / "large.json"
    large.write_bytes(b" " * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(WorkflowValidationError, match="exceeds"):
        load_workflow(large)

    with pytest.raises(WorkflowValidationError, match="workflow root"):
        parse_workflow_bytes(b"[]")
    with pytest.raises(WorkflowValidationError, match="input root"):
        parse_json_object_bytes(b"[]")
    with pytest.raises(WorkflowValidationError, match="UTF-8"):
        parse_workflow_bytes(b"\xff")
    with pytest.raises(WorkflowValidationError, match="cannot read file"):
        load_workflow(tmp_path / "missing.json")
    with pytest.raises(WorkflowValidationError, match="exceeds"):
        parse_json_object_bytes(b" " * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(WorkflowValidationError, match=r"invalid JSON|input root"):
        parse_json_object_bytes(("[" * 2_000 + "]" * 2_000).encode())


def test_rejects_excessive_nesting_and_reference_cycles() -> None:
    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(22):
        child: dict[str, object] = {}
        cursor["child"] = child
        cursor = child

    document = workflow_document()
    document["defaults"] = nested
    with pytest.raises(WorkflowValidationError, match="nesting depth"):
        Workflow.from_dict(document)

    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    document["defaults"] = cyclic
    with pytest.raises(WorkflowValidationError, match="reference cycle"):
        Workflow.from_dict(document)

    document = workflow_document()
    document["output"] = cyclic
    with pytest.raises(WorkflowValidationError, match="reference cycle"):
        Workflow.from_dict(document)

    very_deep: dict[str, object] = {}
    cursor = very_deep
    for _ in range(2_000):
        child = {}
        cursor["child"] = child
        cursor = child
    document["defaults"] = very_deep
    with pytest.raises(WorkflowValidationError, match="nesting depth"):
        Workflow.from_dict(document)


def test_api_validation_limits_and_fallback_error_message() -> None:
    document = workflow_document()
    document["steps"] = [
        {"id": f"step_{index}", "uses": "set", "with": {}}
        for index in range(MAX_WORKFLOW_STEPS + 1)
    ]
    with pytest.raises(WorkflowValidationError, match="at most"):
        Workflow.from_dict(document)

    document = workflow_document()
    document["defaults"] = {"infinite": float("inf")}
    with pytest.raises(WorkflowValidationError, match="non-finite"):
        Workflow.from_dict(document)

    document["defaults"] = {"long": "x" * 100_001}
    with pytest.raises(WorkflowValidationError, match="string limit"):
        Workflow.from_dict(document)

    document["defaults"] = {str(index): index for index in range(10_001)}
    with pytest.raises(WorkflowValidationError, match="collection limit"):
        Workflow.from_dict(document)

    document["defaults"] = {1: "bad"}
    with pytest.raises(WorkflowValidationError, match="non-string key"):
        Workflow.from_dict(document)

    document["defaults"] = {"x" * 100_001: "bad"}
    with pytest.raises(WorkflowValidationError, match="overlong object key"):
        Workflow.from_dict(document)

    assert str(DirectValidationError([])) == "validation failed"
