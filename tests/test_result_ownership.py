# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Public mutation boundaries and private copy costs for run-owned JSON trees."""

from __future__ import annotations

import copy

import pytest

from samsarix_spirals import Workflow, run_workflow, runner


def ownership_workflow(explicit_output):
    """Exercise every operation, prior-step references, defaults and repeated subtrees."""
    document = {
        "schema_version": 1,
        "name": "ownership",
        "defaults": {"policy": {"tags": ["reviewed"]}},
        "steps": [
            {
                "id": "seed",
                "uses": "set",
                "with": {
                    "payload": "{{ input.payload }}",
                    "policy": "{{ defaults.policy }}",
                    "literal": {"tags": ["literal"]},
                },
            },
            {
                "id": "merged",
                "uses": "merge",
                "with": {
                    "objects": ["{{ steps.seed }}", {"extra": {"tags": ["extra"]}}],
                },
            },
            {
                "id": "selected",
                "uses": "pick",
                "with": {
                    "object": "{{ steps.merged }}",
                    "keys": ["payload", "policy", "extra"],
                },
            },
            {
                "id": "approved",
                "uses": "assert",
                "with": {
                    "value": "{{ steps.selected }}",
                    "operator": "truthy",
                },
            },
            {
                "id": "mapped",
                "uses": "map",
                "with": {
                    "items": "{{ steps.approved.value.payload.rows }}",
                    "template": {"first": "{{ item }}", "again": "{{ item }}"},
                },
            },
            {
                "id": "filtered",
                "uses": "filter",
                "with": {
                    "items": "{{ steps.mapped }}",
                    "where": {
                        "value": "{{ item.first.enabled }}",
                        "operator": "equals",
                        "expected": True,
                    },
                },
            },
            {
                "id": "normalized",
                "uses": "normalize",
                "with": {
                    "value": [" ALPHA ", "Beta"],
                    "transforms": ["trim", "ascii_lower"],
                },
            },
        ],
    }
    if explicit_output:
        document["output"] = {
            "first": "{{ steps.filtered }}",
            "again": "{{ steps.filtered }}",
            "normalized": "{{ steps.normalized }}",
        }
    # Deliberately shared caller-owned containers must be detached at ingress.
    tags = ["source"]
    payload = {
        "payload": {
            "rows": [
                {"enabled": True, "tags": tags},
                {"enabled": False, "tags": tags},
            ]
        }
    }
    return Workflow.from_dict(document), payload


def containers(value):
    """Return all mutable nodes, preserving repeated identities to detect aliases."""
    if isinstance(value, dict):
        return [value, *(node for child in value.values() for node in containers(child))]
    if isinstance(value, list):
        return [value, *(node for child in value for node in containers(child))]
    return []


@pytest.mark.parametrize("explicit_output", [False, True])
def test_no_public_result_trees_share_mutable_nodes(explicit_output):
    """Sharing the private lookup index must never become a public container alias."""
    workflow, payload = ownership_workflow(explicit_output)
    result = run_workflow(workflow, payload)
    next_run = run_workflow(workflow, payload)
    outputs = [
        result.output,
        *[step.output for step in result.steps],
        result.to_dict(),
        *[step.to_dict() for step in result.steps],
        next_run.output,
        *[step.output for step in next_run.steps],
    ]
    owned = set()
    for tree in outputs:
        identities = [id(node) for node in containers(tree)]
        assert len(identities) == len(set(identities)), "aliased occurrence within one output"
        assert owned.isdisjoint(identities), "two public outputs share a mutable node"
        owned.update(identities)
    source_roots = [payload, workflow.defaults, *[step.arguments for step in workflow.steps]]
    for source in source_roots:
        assert owned.isdisjoint(id(node) for node in containers(source))


@pytest.mark.parametrize("explicit_output", [False, True])
@pytest.mark.parametrize("target", range(10))
def test_mutations_do_not_cross_result_input_model_or_run_boundaries(explicit_output, target):
    """Mutate every nested node in a returned tree, then check all other surfaces."""
    workflow, payload = ownership_workflow(explicit_output)
    result = run_workflow(workflow, payload)
    original_result = result.to_dict()
    roots = [
        *[step.output for step in result.steps],
        result.output,
        result.to_dict(),
        result.steps[0].to_dict(),
        payload,
        workflow.to_dict(),
    ]
    other_roots = [root for index, root in enumerate(roots) if index != target]
    expected_others = copy.deepcopy(other_roots)
    for node in containers(roots[target]):
        if isinstance(node, dict):
            node["mutation"] = ["changed"]
        else:
            node.append({"mutation": True})
    assert other_roots == expected_others
    assert run_workflow(workflow, payload).to_dict() == original_result


@pytest.mark.parametrize("count", [1, 20])
def test_private_trace_index_does_not_deepcopy_every_step(monkeypatch, count):
    """Guard the measured cost: only defaults and implicit final output need deepcopy."""
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "copy-cost",
            "steps": [
                {"id": f"step{i}", "uses": "set", "with": {"items": "{{ input.items }}"}}
                for i in range(count)
            ],
        }
    )
    copied_roots = []
    original = copy.deepcopy

    def track(value):
        copied_roots.append(value)
        return original(value)

    monkeypatch.setattr(runner.copy, "deepcopy", track)
    result = run_workflow(workflow, {"items": [{"value": [1]}]})
    assert len(result.steps) == count
    assert len(copied_roots) == 2
    assert copied_roots[0] is workflow.defaults
    assert copied_roots[1] is result.steps[-1].output
