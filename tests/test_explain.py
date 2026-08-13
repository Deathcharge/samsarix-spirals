# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

from samsarix_spirals import Workflow, explain_workflow


def test_explain_reports_direct_dependencies_and_value_free_paths() -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "agent-contract",
            "defaults": {"metadata": {"source": "must-not-appear"}},
            "steps": [
                {
                    "id": "gate",
                    "uses": "assert",
                    "with": {
                        "value": "{{ input.approved }}",
                        "operator": "equals",
                        "expected": True,
                    },
                },
                {
                    "id": "enriched",
                    "uses": "merge",
                    "with": {
                        "objects": [
                            "{{ defaults.metadata }}",
                            "{{ input.result }}",
                            {"review": "{{ steps.gate.passed }}"},
                        ]
                    },
                },
            ],
            "output": {
                "result": "{{ steps.enriched }}",
                "trace": "{{ input.trace_id }}",
            },
        }
    )

    explanation = explain_workflow(workflow)

    assert explanation.to_dict() == {
        "explain_version": 1,
        "workflow": "agent-contract",
        "input_paths": ["input.approved", "input.result", "input.trace_id"],
        "default_paths": ["defaults.metadata"],
        "steps": [
            {
                "id": "gate",
                "uses": "assert",
                "depends_on": [],
                "input_paths": ["input.approved"],
                "default_paths": [],
            },
            {
                "id": "enriched",
                "uses": "merge",
                "depends_on": ["gate"],
                "input_paths": ["input.result"],
                "default_paths": ["defaults.metadata"],
            },
        ],
        "output": {
            "depends_on": ["enriched"],
            "input_paths": ["input.trace_id"],
            "default_paths": [],
        },
    }
    assert "must-not-appear" not in str(explanation.to_dict())


def test_explain_reports_implicit_last_step_output() -> None:
    workflow = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "implicit",
            "steps": [{"id": "value", "uses": "set", "with": {"safe": True}}],
        }
    )

    result = explain_workflow(workflow).to_dict()

    assert result["output"] == {
        "depends_on": ["value"],
        "input_paths": [],
        "default_paths": [],
    }
