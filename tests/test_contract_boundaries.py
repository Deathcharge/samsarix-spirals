# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from samsarix_spirals import (
    Workflow,
    WorkflowExecutionError,
    WorkflowSuite,
    load_suite,
    load_workflow,
    run_suite,
    run_workflow,
)
from samsarix_spirals.cli import main

EXAMPLES = Path(__file__).parents[1] / "examples"


@pytest.mark.parametrize(
    "value,expected,equal",
    [
        (True, 1, False),
        (0, False, False),
        ([True], [1.0], False),
        ({"nested": [False]}, {"nested": [0]}, False),
        (1, 1.0, True),
        ({"nested": [1, None]}, {"nested": [1.0, None]}, True),
        (None, None, True),
        (True, True, True),
        ("1", 1, False),
        ([1], [1, 2], False),
        ({"a": 1}, {"b": 1}, False),
    ],
)
def test_assertions_and_suite_expectations_share_json_equality(value, expected, equal) -> None:
    for operator in ("equals", "not_equals", "contains"):
        workflow = Workflow.from_dict(
            {
                "schema_version": 1,
                "name": "comparison",
                "steps": [
                    {
                        "id": "check",
                        "uses": "assert",
                        "with": {
                            "value": [value] if operator == "contains" else value,
                            "operator": operator,
                            "expected": expected,
                        },
                    }
                ],
            }
        )
        should_pass = not equal if operator == "not_equals" else equal
        if should_pass:
            run_workflow(workflow)
        else:
            with pytest.raises(WorkflowExecutionError) as error:
                run_workflow(workflow)
            assert error.value.step_id == "check"

    identity = Workflow.from_dict(
        {
            "schema_version": 1,
            "name": "identity",
            "steps": [{"id": "noop", "uses": "set", "with": {}}],
            "output": "{{ input.value }}",
        }
    )
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "equality",
            "cases": [
                {"name": "compare", "input": {"value": value}, "expect": {"output": expected}}
            ],
        }
    )
    assert run_suite(identity, suite).successful is equal


@pytest.mark.parametrize("approved", [1, 1.0, "true", None, [], {}])
@pytest.mark.parametrize("name", ["agent-tool-result", "release-policy"])
def test_flagship_approval_requires_a_json_boolean(name, approved) -> None:
    workflow = load_workflow(EXAMPLES / f"{name}.json")
    fixture = copy.deepcopy(load_suite(EXAMPLES / f"{name}.suite.json").cases[0].input)
    fixture["approved"] = approved
    with pytest.raises(WorkflowExecutionError) as error:
        run_workflow(workflow, fixture)
    assert error.value.step_id == "require_approval"


def test_agent_policy_metadata_cannot_be_overridden_by_result() -> None:
    workflow = load_workflow(EXAMPLES / "agent-tool-result.json")
    fixture = copy.deepcopy(load_suite(EXAMPLES / "agent-tool-result.suite.json").cases[0].input)
    fixture["result"].update({"source": "spoofed", "reviewed": False})
    output = run_workflow(workflow, fixture).output
    assert output["source"] == "agent"
    assert output["reviewed"] is True


@pytest.mark.parametrize("compact", [False, True])
def test_final_output_cli_does_not_serialize_intermediate_values(tmp_path, capsys, compact) -> None:
    fixture = load_suite(EXAMPLES / "agent-tool-result.suite.json").cases[0].input
    path = tmp_path / "input.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    args = ["run", str(EXAMPLES / "agent-tool-result.json"), "--input", str(path)]
    if compact:
        args.append("--compact")

    # Trace mode is retained for compatibility, but is not a redaction boundary.
    assert main(args) == 0
    trace = json.loads(capsys.readouterr().out)
    assert trace["steps"][1]["output"]["credential"]

    assert main([*args, "--output-only"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == trace["output"]
    assert "credential" not in captured.out
    assert "must never leave" not in captured.out
    assert "steps" not in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("value", [None, False, 0, "", [], {}, [1, "two"]])
def test_output_only_preserves_any_json_value(tmp_path, capsys, value) -> None:
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "value",
                "steps": [{"id": "noop", "uses": "set", "with": {}}],
                "output": value,
            }
        ),
        encoding="utf-8",
    )
    assert main(["run", str(path), "--output-only"]) == 0
    assert json.loads(capsys.readouterr().out) == value


def test_output_only_failure_has_no_partial_stdout(tmp_path, capsys) -> None:
    path = tmp_path / "input.json"
    path.write_text('{"approved": false}', encoding="utf-8")
    assert (
        main(
            ["run", str(EXAMPLES / "agent-tool-result.json"), "--input", str(path), "--output-only"]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires approval" in captured.err


@pytest.mark.parametrize(
    "section,key,value,step",
    [
        ("repository", "archived", None, "active"),
        ("repository", "archived", 0, "active"),
        ("repository", "visibility", "typo", "private_visibility"),
        ("repository", "visibility", None, "private_visibility"),
        ("protection", "require_code_owner_reviews", "false", "code_owners"),
        ("protection", "require_code_owner_reviews", 1, "code_owners"),
        ("security", "secret_scanning", "false", "secret_scanning"),
        ("security", "secret_scanning", 1, "secret_scanning"),
    ],
)
def test_repository_policy_fails_closed_on_untrusted_types(section, key, value, step) -> None:
    workflow = load_workflow(EXAMPLES / "repository-policy.json")
    fixture = copy.deepcopy(load_suite(EXAMPLES / "repository-policy.suite.json").cases[0].input)
    fixture[section][key] = value
    with pytest.raises(WorkflowExecutionError) as error:
        run_workflow(workflow, fixture)
    assert error.value.step_id == step
