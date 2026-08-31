# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from samsarix_spirals import (
    Workflow,
    WorkflowExecutionError,
    WorkflowValidationError,
    explain_workflow,
    get_schema,
    run_workflow,
    runner,
)
from samsarix_spirals.cli import main


def document(uses, arguments):
    return {
        "schema_version": 1,
        "name": "list-test",
        "steps": [{"id": "shape", "uses": uses, "with": arguments}],
    }


def workflow(uses, arguments):
    source = document(uses, arguments)
    Draft202012Validator(get_schema("workflow")).validate(source)
    return Workflow.from_dict(source)


def test_map_records_preserves_order_and_types_and_detaches():
    w = workflow(
        "map",
        {
            "items": "{{ input.records }}",
            "template": {
                "id": "{{ item.id }}",
                "value": "{{ item.value }}",
                "label": "id={{ item.id }}",
                "tag": "{{ input.tag }}",
            },
        },
    )
    values = [{"id": 2, "value": [None, True], "secret": "excluded"}, {"id": 2, "value": []}]
    result = run_workflow(w, {"records": values, "tag": "reviewed"})
    assert result.output == [
        {"id": 2, "value": [None, True], "label": "id=2", "tag": "reviewed"},
        {"id": 2, "value": [], "label": "id=2", "tag": "reviewed"},
    ]
    result.output[0]["value"].append(0)
    assert values[0]["value"] == [None, True]
    assert result.steps[0].output[0]["value"] == [None, True]


@pytest.mark.parametrize(
    "template,expected", [("{{ item }}", [1, None, False]), (None, [None] * 3)]
)
def test_map_scalar_and_null_templates(template, expected):
    assert (
        run_workflow(workflow("map", {"items": [1, None, False], "template": template})).output
        == expected
    )


def test_map_uses_defaults_prior_steps_and_reports_local_paths():
    source = document(
        "map",
        {
            "items": "{{ input.rows }}",
            "template": {
                "text": "{{ defaults.prefix }}{{ item.name }}{{ steps.first.suffix }}",
            },
        },
    )
    source["defaults"] = {"prefix": "hello "}
    source["steps"].insert(0, {"id": "first", "uses": "set", "with": {"suffix": "!"}})
    w = Workflow.from_dict(source)
    assert run_workflow(w, {"rows": [{"name": "Ada"}]}).output == [{"text": "hello Ada!"}]
    explanation = explain_workflow(w).to_dict()
    assert explanation["steps"][1]["item_paths"] == ["item.name"]
    assert explanation["steps"][1]["depends_on"] == ["first"]
    assert explanation["input_paths"] == ["input.rows"]
    assert "item_paths" not in explanation["steps"][0]


@pytest.mark.parametrize(
    "uses,body",
    [
        ("map", {"template": "{{ item.missing }}"}),
        ("filter", {"where": {"value": "{{ item.missing }}", "operator": "truthy"}}),
    ],
)
def test_empty_lists_succeed_but_missing_fields_on_nonempty_lists_fail(uses, body):
    w = workflow(uses, {"items": "{{ input.rows }}", **body})
    assert run_workflow(w, {"rows": []}).output == []
    with pytest.raises(WorkflowExecutionError, match=r"item\[0\].*missing") as error:
        run_workflow(w, {"rows": [{}]})
    assert error.value.step_id == "shape"
    with pytest.raises(WorkflowExecutionError, match="must render to an array"):
        run_workflow(w, {"rows": {}})


def test_filter_uses_json_equality_and_preserves_duplicates():
    w = workflow(
        "filter",
        {
            "items": "{{ input.rows }}",
            "where": {
                "value": "{{ item.enabled }}",
                "operator": "equals",
                "expected": True,
            },
        },
    )
    data = [
        {"enabled": True, "id": 1},
        {"enabled": 1},
        {"enabled": "true"},
        {"enabled": False},
        {"enabled": True, "id": 1},
    ]
    assert run_workflow(w, {"rows": data}).output == [data[0], data[-1]]


@pytest.mark.parametrize(
    "operator,expected,output",
    [
        ("greater_than", 2, [3]),
        ("contains", "x", ["xx"]),
        ("falsy", None, [None, False, ""]),
    ],
)
def test_filter_reuses_comparison_semantics(operator, expected, output):
    values = (
        [1, 2, 3]
        if operator == "greater_than"
        else (["xx", "yy"] if operator == "contains" else [None, False, "", "x"])
    )
    w = workflow(
        "filter",
        {
            "items": values,
            "where": {"value": "{{ item }}", "operator": operator, "expected": expected},
        },
    )
    assert run_workflow(w).output == output


def test_filter_invalid_comparison_is_error_not_silent_exclusion():
    w = workflow(
        "filter",
        {
            "items": ["ok", 1],
            "where": {"value": "{{ item }}", "operator": "contains", "expected": "o"},
        },
    )
    with pytest.raises(WorkflowExecutionError, match=r"item\[1\].*requires"):
        run_workflow(w)


@pytest.mark.parametrize(
    "value,transforms,expected",
    [
        (" \tHELLO\r\n", ["trim", "ascii_lower"], "hello"),
        ([" One ", " TWO", ""], ["trim", "ascii_upper"], ["ONE", "TWO", ""]),
        ("aB", ["ascii_lower", "ascii_upper"], "AB"),
        ("aB", ["ascii_upper", "ascii_lower"], "ab"),
        ("\u00a0ÉßZ\u00a0", ["trim", "ascii_lower"], "\u00a0Éßz\u00a0"),
        ([], ["trim"], []),
    ],
)
def test_normalize_is_ordered_ascii_only(value, transforms, expected):
    assert (
        run_workflow(workflow("normalize", {"value": value, "transforms": transforms})).output
        == expected
    )


@pytest.mark.parametrize("value", [None, 12, {}, ["valid", False]])
def test_normalize_rejects_rendered_nonstrings(value):
    w = workflow("normalize", {"value": "{{ input.value }}", "transforms": ["trim"]})
    with pytest.raises(WorkflowExecutionError, match="must be a string"):
        run_workflow(w, {"value": value})


@pytest.mark.parametrize(
    "uses,args",
    [
        ("map", {"items": []}),
        ("map", {"template": None}),
        ("map", {"items": {}, "template": None}),
        ("map", {"items": [], "template": None, "extra": True}),
        ("filter", {"items": []}),
        ("filter", {"items": [], "where": None}),
        ("filter", {"items": [], "where": {"value": 1, "operator": "equals"}}),
        ("filter", {"items": [], "where": {"operator": "truthy"}}),
        ("filter", {"items": [], "where": {"value": 1, "operator": "invalid"}}),
        ("filter", {"items": [], "where": {"value": 1, "operator": "truthy", "message": "no"}}),
        ("normalize", {"transforms": ["trim"]}),
        ("normalize", {"value": 1, "transforms": ["trim"]}),
        ("normalize", {"value": [1], "transforms": ["trim"]}),
        ("normalize", {"value": "ok", "transforms": []}),
        ("normalize", {"value": "ok", "transforms": ["trim"] * 4}),
        ("normalize", {"value": "ok", "transforms": ["lower"]}),
        ("normalize", {"value": "ok", "transforms": [1]}),
        ("normalize", {"value": "ok", "transforms": "{{ input.transforms }}"}),
    ],
)
def test_invalid_operation_shapes_are_rejected_by_runtime_and_schema(uses, args):
    source = document(uses, args)
    with pytest.raises(WorkflowValidationError):
        Workflow.from_dict(source)
    assert list(Draft202012Validator(get_schema("workflow")).iter_errors(source))


@pytest.mark.parametrize(
    "uses,args",
    [
        ("map", {"items": "{{ item }}", "template": None}),
        ("filter", {"items": "{{ item }}", "where": {"value": True, "operator": "truthy"}}),
        ("set", {"value": "{{ item }}"}),
        ("normalize", {"value": "{{ item }}", "transforms": ["trim"]}),
        ("map", {"items": [], "template": "{{ steps.later }}"}),
        ("map", {"items": [], "template": "{{ environment.secret }}"}),
        ("map", {"items": [], "template": "{{item.bad syntax}}"}),
    ],
)
def test_item_scope_and_existing_reference_checks_cannot_be_bypassed(uses, args):
    with pytest.raises(WorkflowValidationError):
        Workflow.from_dict(document(uses, args))


def test_item_scope_does_not_escape_to_final_output():
    source = document("map", {"items": [1], "template": "{{ item }}"})
    source["output"] = "{{ item }}"
    with pytest.raises(WorkflowValidationError, match="unsupported template root"):
        Workflow.from_dict(source)


def test_map_data_is_not_reinterpreted_as_templates():
    w = workflow("map", {"items": "{{ input.rows }}", "template": "{{ item }}"})
    assert run_workflow(w, {"rows": ["{{ input.secret }}"]}).output == ["{{ input.secret }}"]


def test_map_shares_value_and_byte_budgets_across_items(monkeypatch):
    w = workflow("map", {"items": [1, 2], "template": "{{ input.text }}"})
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", 13)
    assert run_workflow(w, {"text": "abc"}).output == ["abc", "abc"]
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", 12)
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(w, {"text": "abc"})
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", 4_194_304)
    large = workflow("map", {"items": [1] * 10, "template": "{{ input.many }}"})
    with pytest.raises(WorkflowExecutionError, match="value limit"):
        run_workflow(large, {"many": [0] * 6000})


def test_filter_predicates_share_budget_even_for_excluded_items(monkeypatch):
    w = workflow(
        "filter", {"items": [0] * 20, "where": {"value": "{{ input.value }}", "operator": "falsy"}}
    )
    monkeypatch.setattr(runner, "MAX_RENDERED_BYTES", 200)
    with pytest.raises(WorkflowExecutionError, match="byte limit"):
        run_workflow(w, {"value": "x" * 50})


def test_map_output_depth_includes_array_root():
    template = "{{ item }}"
    for _ in range(19):
        template = {"value": template}
    w = workflow("map", {"items": "{{ input.rows }}", "template": template})
    assert run_workflow(w, {"rows": [1]}).output
    with pytest.raises(WorkflowExecutionError, match="nesting limit"):
        run_workflow(w, {"rows": [{"wrapped": 1}]})


def test_cli_list_failure_never_emits_partial_results(tmp_path, capsys):
    path = tmp_path / "map.json"
    path.write_text(
        json.dumps(document("map", {"items": [{"id": 1}, {}], "template": "{{ item.id }}"})),
        encoding="utf-8",
    )
    assert main(["run", str(path), "--output-only"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "item[1]" in captured.err


def test_collection_limit_and_cumulative_run_budget_still_apply(monkeypatch):
    w = workflow("map", {"items": "{{ input.rows }}", "template": "{{ item }}"})
    assert len(run_workflow(w, {"rows": [0] * 10_000}).output) == 10_000
    with pytest.raises(WorkflowValidationError, match="item collection limit"):
        run_workflow(w, {"rows": [0] * 10_001})
    monkeypatch.setattr(runner, "MAX_RUN_OUTPUT_BYTES", 5)
    # [0] is three bytes; the implicit final copy must count again.
    with pytest.raises(WorkflowExecutionError, match="combined output"):
        run_workflow(w, {"rows": [0]})


def test_large_map_bytes_fail_under_real_limits():
    w = workflow("map", {"items": [0] * 50, "template": "{{ input.text }}"})
    with pytest.raises(WorkflowExecutionError, match="4194304-byte limit"):
        run_workflow(w, {"text": "x" * 100_000})


def test_filter_predicate_nodes_share_budget():
    w = workflow(
        "filter",
        {
            "items": [0] * 10,
            "where": {
                "value": "{{ input.many }}",
                "operator": "equals",
                "expected": [],
            },
        },
    )
    with pytest.raises(WorkflowExecutionError, match="50000-value limit"):
        run_workflow(w, {"many": [0] * 6000})


def test_normalize_does_not_evaluate_template_text_from_input():
    w = workflow("normalize", {"value": "{{ input.text }}", "transforms": ["trim"]})
    assert run_workflow(w, {"text": " {{ input.secret }} "}).output == "{{ input.secret }}"


def test_shared_predicate_validation_keeps_accurate_argument_paths():
    with pytest.raises(WorkflowValidationError) as error:
        Workflow.from_dict(document("assert", {"value": True, "operator": "truthy", "extra": 1}))
    assert error.value.issues == ("$.steps[0].with contains unknown field 'extra'",)
