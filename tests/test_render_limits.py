# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import pytest

from samsarix_spirals import Workflow, WorkflowExecutionError, run_workflow


def nest(value: object, levels: int, kind: str = "object") -> object:
    for _ in range(levels):
        value = {"wrap": value} if kind == "object" else [value]
    return value


@pytest.mark.parametrize("kind", ["object", "array"])
def test_template_composition_preserves_depth_limit(kind: str) -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "compose",
            "steps": [
                {
                    "id": "wrap",
                    "uses": "set",
                    "with": {"value": nest("{{ input.payload }}", 11, kind)},
                }
            ],
        }
    )
    with pytest.raises(WorkflowExecutionError, match="nesting limit") as error:
        run_workflow(workflow, {"payload": nest(0, 12, kind)})
    assert error.value.step_id == "wrap"


@pytest.mark.parametrize("kind", ["object", "array"])
def test_final_output_composition_preserves_depth_limit(kind: str) -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "final-compose",
            "steps": [{"id": "noop", "uses": "set", "with": {}}],
            "output": nest("{{ input.payload }}", 12, kind),
        }
    )
    with pytest.raises(WorkflowExecutionError, match="nesting limit") as error:
        run_workflow(workflow, {"payload": nest(0, 12, kind)})
    assert error.value.step_id is None


@pytest.mark.parametrize("kind", ["object", "array"])
def test_exact_depth_boundary_is_accepted(kind: str) -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "boundary",
            "steps": [
                {
                    "id": "wrap",
                    "uses": "set",
                    "with": {"value": nest("{{ input.payload }}", 9, kind)},
                }
            ],
        }
    )
    result = run_workflow(workflow, {"payload": nest(0, 10, kind)})
    assert result.output == {"value": nest(0, 19, kind)}


def test_prior_step_reference_cannot_grow_beyond_depth_limit() -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "chain",
            "steps": [
                {"id": "first", "uses": "set", "with": {"value": nest(0, 19)}},
                {"id": "second", "uses": "set", "with": {"value": "{{ steps.first }}"}},
            ],
        }
    )
    with pytest.raises(WorkflowExecutionError, match="nesting limit") as error:
        run_workflow(workflow)
    assert error.value.step_id == "second"


def test_merge_enforces_combined_collection_limit() -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "merge-limit",
            "steps": [{"id": "merge", "uses": "merge", "with": {"objects": "{{ input.objects }}"}}],
        }
    )
    objects = [
        {str(index): 0 for index in range(6000)},
        {str(index): 0 for index in range(6000, 12000)},
    ]
    with pytest.raises(WorkflowExecutionError, match="key limit") as error:
        run_workflow(workflow, {"objects": objects})
    assert error.value.step_id == "merge"
