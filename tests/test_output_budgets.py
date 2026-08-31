# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json
import sys
from types import MappingProxyType

import pytest

from samsarix_spirals import (
    Workflow,
    WorkflowExecutionError,
    WorkflowSuite,
    run_suite,
    run_workflow,
    runner,
)
from samsarix_spirals.cli import main


def expansion_document(count=50, *, steps=1, explicit_output=False):
    document = {
        "schema_version": 1,
        "name": "byte-budget",
        "steps": [
            {
                "id": f"expand{index}",
                "uses": "set",
                "with": {"items": ["{{ input.text }}"] * count},
            }
            for index in range(steps)
        ],
    }
    if explicit_output:
        document["output"] = {"items": ["{{ input.text }}"] * 50}
    return document


@pytest.mark.parametrize(
    "text,count", [("x" * 100_000, 50), ("\U0001f600" * 100_000, 4)], ids=["ascii", "non-bmp"]
)
def test_repeated_strings_fail_before_large_output(text, count):
    workflow = Workflow.from_dict(expansion_document(count))
    with pytest.raises(WorkflowExecutionError, match=r"rendered.*byte limit") as error:
        run_workflow(workflow, {"text": text})
    assert error.value.step_id == "expand0"


def test_combined_step_outputs_are_bounded():
    workflow = Workflow.from_dict(expansion_document(30, steps=6))
    with pytest.raises(WorkflowExecutionError, match=r"combined output.*byte limit") as error:
        run_workflow(workflow, {"text": "x" * 100_000})
    assert error.value.step_id == "expand5"


@pytest.mark.parametrize("explicit", [False, True])
def test_final_output_counts_even_when_it_repeats_the_last_step(explicit):
    document = expansion_document(30, steps=5)
    if explicit:
        document["output"] = "{{ steps.expand4 }}"
    workflow = Workflow.from_dict(document)
    with pytest.raises(WorkflowExecutionError, match=r"combined output.*byte limit") as error:
        run_workflow(workflow, {"text": "x" * 100_000})
    assert error.value.step_id is None


def test_explicit_final_render_has_its_own_byte_limit():
    workflow = Workflow.from_dict(expansion_document(1, explicit_output=True))
    with pytest.raises(WorkflowExecutionError, match=r"rendered.*byte limit") as error:
        run_workflow(workflow, {"text": "x" * 100_000})
    assert error.value.step_id is None


@pytest.mark.parametrize("output_only", [False, True])
@pytest.mark.parametrize("compact", [False, True])
def test_cli_size_failure_has_no_partial_output(tmp_path, capsys, output_only, compact):
    workflow_path = tmp_path / "workflow.json"
    input_path = tmp_path / "input.json"
    workflow_path.write_text(json.dumps(expansion_document()), encoding="utf-8")
    input_path.write_text(json.dumps({"text": "x" * 100_000}), encoding="utf-8")
    arguments = ["run", str(workflow_path), "--input", str(input_path)]
    if output_only:
        arguments.append("--output-only")
    if compact:
        arguments.append("--compact")
    assert main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "byte limit" in captured.err
    assert "expand0" in captured.err


@pytest.mark.parametrize("source", ["input", "defaults"])
def test_api_tuple_expansion_cannot_bypass_accounting(source):
    document = expansion_document(1)
    document["steps"][0]["with"] = {"items": "{{ " + source + ".items }}"}
    payload = {"items": ("x" * 100_000,) * 50}
    if source == "defaults":
        document["defaults"] = payload
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(Workflow.from_dict(document), payload)


def test_supported_api_collections_are_detached_as_json():
    original = [1]
    document = expansion_document(1)
    document["steps"][0]["with"] = {"items": "{{ input.items }}"}
    payload = {"items": (MappingProxyType({"value": original}),)}
    result = run_workflow(Workflow.from_dict(document), payload)
    assert result.output == {"items": [{"value": [1]}]}
    result.output["items"][0]["value"].append(2)
    assert original == [1]
    assert result.steps[0].output == {"items": [{"value": [1]}]}


@pytest.mark.parametrize("value", [None, True, False, 12, -3.25, 'a\n"\\é😀', [], {}, [1, None]])
def test_render_byte_limit_is_exact_for_scalars_keys_and_punctuation(monkeypatch, value):
    arguments = {"é\n": value}
    size = len(json.dumps(arguments, ensure_ascii=True, separators=(",", ":")))
    document = expansion_document(1)
    document["steps"][0]["with"] = arguments
    workflow = Workflow.from_dict(document)
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", size)
    assert run_workflow(workflow).output == arguments
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", size - 1)
    with pytest.raises(WorkflowExecutionError, match=r"rendered.*byte limit"):
        run_workflow(workflow)


def test_combined_limit_is_inclusive_and_resets_for_every_run_and_suite_case(monkeypatch):
    document = expansion_document(1)
    document["steps"][0]["with"] = {"value": "{{ input.value }}"}
    workflow = Workflow.from_dict(document)
    output = {"value": "é"}
    size = len(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
    monkeypatch.setattr(runner, "MAX_RUN_OUTPUT_BYTES", 2 * size)
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "budget-reset",
            "cases": [
                {"name": str(i), "input": output, "expect": {"output": output}} for i in range(2)
            ],
        }
    )
    assert run_suite(workflow, suite).successful
    monkeypatch.setattr(runner, "MAX_RUN_OUTPUT_BYTES", 2 * size - 1)
    with pytest.raises(WorkflowExecutionError, match=r"combined output.*byte limit"):
        run_workflow(workflow, output)


def test_suite_can_expect_a_size_failure():
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "oversize",
            "cases": [
                {
                    "name": "reject amplification",
                    "input": {"text": "x" * 100_000},
                    "expect": {"error": {"step_id": "expand0", "message_contains": "byte limit"}},
                }
            ],
        }
    )
    assert run_suite(Workflow.from_dict(expansion_document()), suite).successful


@pytest.mark.parametrize("template", ["{{ input.value }}", "number={{ input.value }}"])
def test_unencodable_api_integer_is_an_execution_error(template):
    document = expansion_document(1)
    document["steps"][0]["with"] = {"value": template}
    previous_limit = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(4300)
        with pytest.raises(WorkflowExecutionError, match="cannot be encoded") as error:
            run_workflow(Workflow.from_dict(document), {"value": 10**5000})
        assert error.value.step_id == "expand0"
    finally:
        sys.set_int_max_str_digits(previous_limit)


@pytest.mark.parametrize("source", ["literal", "exact", "embedded"])
def test_all_string_render_paths_count_bytes(monkeypatch, source):
    value = "é\n😀"
    templates = {"literal": value, "exact": "{{ input.text }}", "embedded": "é\n{{ input.text }}"}
    document = expansion_document(1)
    document["steps"][0]["with"] = {"value": templates[source]}
    payload = {"text": "😀" if source == "embedded" else value}
    expected = {"value": value}
    size = len(json.dumps(expected, ensure_ascii=True, separators=(",", ":")))
    workflow = Workflow.from_dict(document)
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", size)
    assert run_workflow(workflow, payload).output == expected
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", size - 1)
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(workflow, payload)


@pytest.mark.parametrize("source", ["literal", "exact"])
def test_large_keys_are_charged(monkeypatch, source):
    document = expansion_document(1)
    value = {"x" * 90: 0, "y" * 90: 1}
    document["steps"][0]["with"] = {"object": value if source == "literal" else "{{ input }}"}
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", 100)
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(Workflow.from_dict(document), value)


@pytest.mark.parametrize("uses", ["assert", "merge", "pick"])
def test_discarded_arguments_still_obey_render_budget(uses):
    many = ["{{ input.text }}"] * 50
    arguments = {
        "assert": {"value": many, "operator": "truthy"},
        "merge": {"objects": [{"value": item} for item in many]},
        "pick": {"object": {"discarded": many}, "keys": []},
    }
    document = expansion_document(1)
    document["steps"][0].update({"uses": uses, "with": arguments[uses]})
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(Workflow.from_dict(document), {"text": "x" * 100_000})


def test_tuple_suite_expectations_and_workflow_literals_normalize_consistently():
    document = expansion_document(1)
    document["steps"][0]["with"] = {"value": (1, MappingProxyType({"flag": True}))}
    document["output"] = ("{{ steps.expand0.value }}",)
    workflow = Workflow.from_dict(document)
    suite = WorkflowSuite.from_dict(
        {
            "suite_version": 1,
            "name": "api-containers",
            "cases": [{"name": "normalized", "expect": {"output": ((1, {"flag": True}),)}}],
        }
    )
    assert run_suite(workflow, suite).successful
    assert workflow.to_dict()["output"] == ["{{ steps.expand0.value }}"]
