# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from samsarix_spirals import Workflow, WorkflowSuite, get_schema

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_bundled_schemas_are_valid_draft_2020_12_and_detached() -> None:
    for name in ("workflow", "suite"):
        schema = get_schema(name)  # type: ignore[arg-type]
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    first = get_schema("workflow")
    first["title"] = "changed"
    assert get_schema("workflow")["title"] == "Samsarix Spirals workflow version 1"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda path: path.name)
def test_examples_match_their_published_schema(path: Path) -> None:
    if path.name.endswith(".input.json"):
        pytest.skip("input fixtures do not use a published document schema")
    document = json.loads(path.read_text(encoding="utf-8"))
    if path.name.endswith(".suite.json"):
        Draft202012Validator(get_schema("suite")).validate(document)
        WorkflowSuite.from_dict(document)
    else:
        Draft202012Validator(get_schema("workflow")).validate(document)
        Workflow.from_dict(document)


def test_workflow_schema_requires_expected_for_comparison_operator() -> None:
    document = {
        "schema_version": 1,
        "name": "invalid",
        "steps": [
            {
                "id": "comparison",
                "uses": "assert",
                "with": {"value": 1, "operator": "equals"},
            }
        ],
    }

    errors = list(Draft202012Validator(get_schema("workflow")).iter_errors(document))

    assert errors
    assert any("'expected' is a required property" in message for message in _messages(errors[0]))


def _messages(error: ValidationError) -> list[str]:
    return [error.message, *(message for child in error.context for message in _messages(child))]
