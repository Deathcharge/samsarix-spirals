# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import copy

import pytest

from samsarix_spirals import (
    Workflow,
    WorkflowExecutionError,
    WorkflowValidationError,
    run_workflow,
)


def workflow_with_steps(steps: list[dict[str, object]], output: object = None) -> Workflow:
    document: dict[str, object] = {
        "schema_version": 1,
        "name": "runner-test",
        "steps": steps,
    }
    if output is not None:
        document["output"] = output
    return Workflow.from_dict(document)


def test_renders_scalars_collections_indexes_and_prior_steps() -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "shape",
                "uses": "set",
                "with": {
                    "message": "Hi {{ input.people.0.name }}",
                    "people": "{{ input.people }}",
                    "active": "{{ input.active }}",
                    "missing_text": "value={{ input.none }}",
                },
            },
            {
                "id": "copy",
                "uses": "set",
                "with": {"result": "{{ steps.shape }}"},
            },
        ],
        {"copied": "{{ steps.copy.result }}"},
    )
    input_data = {"people": [{"name": "Ada"}], "active": True, "none": None}

    result = run_workflow(workflow, input_data)

    assert result.output == {
        "copied": {
            "message": "Hi Ada",
            "people": [{"name": "Ada"}],
            "active": True,
            "missing_text": "value=null",
        }
    }
    assert result.to_dict()["status"] == "completed"
    assert [step.operation for step in result.steps] == ["set", "set"]
    assert input_data == {"people": [{"name": "Ada"}], "active": True, "none": None}


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        ("equals", 2, 2),
        ("not_equals", 2, 3),
        ("truthy", "yes", None),
        ("falsy", "", None),
        ("not_empty", [1], None),
        ("contains", ["a", "b"], "b"),
        ("contains", {"key": 1}, "key"),
        ("contains", "hello", "ell"),
        ("greater_than", 3, 2),
        ("greater_or_equal", 3, 3),
        ("less_than", "a", "b"),
        ("less_or_equal", 2.0, 2.0),
    ],
)
def test_assert_operators(operator: str, value: object, expected: object) -> None:
    arguments: dict[str, object] = {"value": value, "operator": operator}
    if expected is not None:
        arguments["expected"] = expected
    workflow = workflow_with_steps([{"id": "check", "uses": "assert", "with": arguments}])

    result = run_workflow(workflow)

    assert result.output == {"passed": True, "value": value}


def test_failed_assertion_is_fail_fast() -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "check",
                "uses": "assert",
                "with": {
                    "value": 1,
                    "operator": "equals",
                    "expected": 2,
                    "message": "numbers differ",
                },
            },
            {"id": "never", "uses": "set", "with": {"ran": True}},
        ]
    )

    with pytest.raises(WorkflowExecutionError, match="numbers differ") as error:
        run_workflow(workflow)
    assert error.value.step_id == "check"


@pytest.mark.parametrize(
    "value,operator,expected,message",
    [
        (1, "contains", 1, "requires a string, array, or object"),
        ("abc", "contains", 1, "string expected value"),
        ({"key": 1}, "contains", 1, "string expected key"),
        (True, "greater_than", False, "does not compare booleans"),
        (1, "less_than", "2", "same numeric or string type"),
    ],
)
def test_invalid_runtime_comparisons(
    value: object, operator: str, expected: object, message: str
) -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "check",
                "uses": "assert",
                "with": {"value": value, "operator": operator, "expected": expected},
            }
        ]
    )

    with pytest.raises(WorkflowExecutionError, match=message):
        run_workflow(workflow)


def test_reports_missing_paths_and_invalid_embedding() -> None:
    missing = workflow_with_steps(
        [{"id": "step", "uses": "set", "with": {"value": "{{ input.missing }}"}}]
    )
    with pytest.raises(WorkflowExecutionError, match="is missing"):
        run_workflow(missing)

    embedded = workflow_with_steps(
        [{"id": "step", "uses": "set", "with": {"value": "items={{ input.items }}"}}]
    )
    with pytest.raises(WorkflowExecutionError, match="exact template placeholder"):
        run_workflow(embedded, {"items": [1]})

    index = workflow_with_steps(
        [{"id": "step", "uses": "set", "with": {"value": "{{ input.items.2 }}"}}]
    )
    with pytest.raises(WorkflowExecutionError, match="out-of-range"):
        run_workflow(index, {"items": [1]})

    traversal = workflow_with_steps(
        [{"id": "step", "uses": "set", "with": {"value": "{{ input.name.first }}"}}]
    )
    with pytest.raises(WorkflowExecutionError, match="cannot traverse"):
        run_workflow(traversal, {"name": "Ada"})


def test_embedded_boolean_and_additional_ordered_branches() -> None:
    rendered = workflow_with_steps(
        [{"id": "step", "uses": "set", "with": {"value": "active={{ input.active }}"}}]
    )
    assert run_workflow(rendered, {"active": False}).output == {"value": "active=false"}

    for operator, value, expected in [
        ("greater_than", "b", "a"),
        ("greater_or_equal", "a", "a"),
        ("less_or_equal", "a", "a"),
        ("less_than", 1, 2),
    ]:
        workflow = workflow_with_steps(
            [
                {
                    "id": "check",
                    "uses": "assert",
                    "with": {"value": value, "operator": operator, "expected": expected},
                }
            ]
        )
        assert run_workflow(workflow).output == {"passed": True, "value": value}


def test_default_output_is_last_step_and_result_is_detached() -> None:
    workflow = workflow_with_steps([{"id": "step", "uses": "set", "with": {"items": [1]}}])

    first = run_workflow(workflow)
    second = run_workflow(workflow)

    assert first.to_dict() == second.to_dict()
    detached = copy.deepcopy(first.to_dict())
    detached["output"]["items"].append(2)  # type: ignore[index,union-attr]
    assert first.output == {"items": [1]}


def test_merge_is_left_to_right_and_does_not_mutate_input() -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "combined",
                "uses": "merge",
                "with": {
                    "objects": [
                        "{{ input.base }}",
                        {"status": "reviewed", "owner": "{{ input.owner }}"},
                        "{{ input.override }}",
                    ]
                },
            }
        ]
    )
    input_data = {
        "base": {"id": 7, "status": "draft", "nested": {"value": 1}},
        "owner": "Ada",
        "override": {"status": "approved"},
    }

    result = run_workflow(workflow, input_data)

    assert result.output == {
        "id": 7,
        "status": "approved",
        "nested": {"value": 1},
        "owner": "Ada",
    }
    assert input_data["base"] == {"id": 7, "status": "draft", "nested": {"value": 1}}


def test_pick_allowlists_keys_and_can_skip_missing_optional_keys() -> None:
    required = workflow_with_steps(
        [
            {
                "id": "public",
                "uses": "pick",
                "with": {
                    "object": "{{ input.payload }}",
                    "keys": ["id", "summary"],
                },
            }
        ]
    )
    optional = workflow_with_steps(
        [
            {
                "id": "public",
                "uses": "pick",
                "with": {
                    "object": "{{ input.payload }}",
                    "keys": ["id", "missing"],
                    "required": False,
                },
            }
        ]
    )
    payload = {"id": 7, "summary": "safe", "secret": "do not expose"}

    assert run_workflow(required, {"payload": payload}).output == {"id": 7, "summary": "safe"}
    assert run_workflow(optional, {"payload": payload}).output == {"id": 7}


@pytest.mark.parametrize(
    "uses,arguments,message",
    [
        ("merge", {"objects": "{{ input.objects }}"}, "must render to an array"),
        (
            "merge",
            {"objects": "{{ input.objects_with_scalar }}"},
            r"objects\[1\] must render to an object",
        ),
        (
            "pick",
            {"object": "{{ input.not_object }}", "keys": []},
            "object must render to an object",
        ),
        ("pick", {"object": {}, "keys": "{{ input.not_keys }}"}, "keys must render to an array"),
        (
            "pick",
            {"object": {"id": 1}, "keys": "{{ input.non_string_keys }}"},
            r"keys\[0\] must render to a string",
        ),
        ("pick", {"object": {"id": 1}, "keys": ["id", "id"]}, "is duplicated"),
        ("pick", {"object": {"id": 1}, "keys": ["missing"]}, "missing required key"),
    ],
)
def test_object_shaping_runtime_errors(
    uses: str, arguments: dict[str, object], message: str
) -> None:
    workflow = workflow_with_steps([{"id": "shape", "uses": uses, "with": arguments}])

    with pytest.raises(WorkflowExecutionError, match=message):
        run_workflow(
            workflow,
            {
                "objects": {},
                "objects_with_scalar": [{}, 1],
                "not_object": [],
                "not_keys": {},
                "non_string_keys": [1],
            },
        )


def test_pick_required_template_must_render_to_boolean() -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "shape",
                "uses": "pick",
                "with": {
                    "object": {},
                    "keys": [],
                    "required": "{{ input.required }}",
                },
            }
        ]
    )

    with pytest.raises(WorkflowExecutionError, match="must render to a boolean"):
        run_workflow(workflow, {"required": "yes"})


def test_run_limits_and_input_validation() -> None:
    workflow = workflow_with_steps(
        [
            {"id": "one", "uses": "set", "with": {}},
            {"id": "two", "uses": "set", "with": {}},
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="exceeding the run limit"):
        run_workflow(workflow, max_steps=1)
    with pytest.raises(WorkflowExecutionError, match="max_steps"):
        run_workflow(workflow, max_steps=0)

    invalid_input = {"value": object()}
    with pytest.raises(WorkflowValidationError, match="unsupported value type"):
        run_workflow(workflow, invalid_input)


def test_render_budgets_prevent_output_amplification() -> None:
    string_amplification = workflow_with_steps(
        [
            {
                "id": "expand",
                "uses": "set",
                "with": {"value": "{{ input.large }}{{ input.large }}"},
            }
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="rendered string exceeds"):
        run_workflow(string_amplification, {"large": "x" * 60_000})

    node_amplification = workflow_with_steps(
        [
            {
                "id": "expand",
                "uses": "set",
                "with": {str(index): "{{ input.items }}" for index in range(6)},
            }
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="rendered value exceeds"):
        run_workflow(node_amplification, {"items": list(range(9_000))})


def test_oversized_template_index_fails_as_an_expected_error() -> None:
    workflow = workflow_with_steps(
        [
            {
                "id": "index",
                "uses": "set",
                "with": {"value": "{{ input.items." + "9" * 5_000 + " }}"},
            }
        ]
    )

    with pytest.raises(WorkflowExecutionError, match="oversized array index"):
        run_workflow(workflow, {"items": [1]})
