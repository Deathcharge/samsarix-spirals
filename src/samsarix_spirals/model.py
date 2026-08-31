# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Workflow data model and bounded JSON loading."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

from .errors import WorkflowValidationError

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

SCHEMA_VERSION = 1
MAX_DOCUMENT_BYTES = 1_048_576
MAX_NESTING = 20
MAX_COLLECTION_ITEMS = 10_000
MAX_JSON_VALUES = 50_000
MAX_STRING_LENGTH = 100_000
MAX_WORKFLOW_STEPS = 1_000
DEFAULT_MAX_RUN_STEPS = 100

STEP_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*)\s*}}")
SUPPORTED_OPERATIONS = frozenset({"assert", "merge", "pick", "set"})
ASSERT_OPERATORS = frozenset(
    {
        "contains",
        "equals",
        "falsy",
        "greater_or_equal",
        "greater_than",
        "less_or_equal",
        "less_than",
        "not_empty",
        "not_equals",
        "truthy",
    }
)


@dataclass(frozen=True, slots=True)
class Step:
    """A validated workflow step."""

    id: str
    uses: str
    arguments: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Workflow:
    """A validated version 1 Samsarix Spirals workflow."""

    schema_version: int
    name: str
    description: str | None
    defaults: dict[str, JsonValue]
    steps: tuple[Step, ...]
    output: JsonValue
    output_defined: bool

    @classmethod
    def from_dict(cls, document: Mapping[str, object]) -> Workflow:
        """Validate and copy a workflow mapping."""
        issues: list[str] = []
        allowed = {"schema_version", "name", "description", "defaults", "steps", "output"}
        _reject_unknown_keys(document, allowed, "$", issues)

        schema_version = document.get("schema_version")
        if schema_version != SCHEMA_VERSION or isinstance(schema_version, bool):
            issues.append(f"$.schema_version must be the integer {SCHEMA_VERSION}")

        name = document.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append("$.name must be a non-empty string")
        elif len(name) > 100:
            issues.append("$.name must contain at most 100 characters")

        description = document.get("description")
        if description is not None and not isinstance(description, str):
            issues.append("$.description must be a string or null")
        elif isinstance(description, str) and len(description) > 500:
            issues.append("$.description must contain at most 500 characters")

        raw_defaults = document.get("defaults", {})
        if not isinstance(raw_defaults, Mapping):
            issues.append("$.defaults must be an object")
            raw_defaults = {}
        _validate_json_value(raw_defaults, "$.defaults", issues)
        defaults_valid = not any(issue.startswith("$.defaults") for issue in issues)
        defaults = (
            cast(dict[str, JsonValue], _copy_json_value(raw_defaults)) if defaults_valid else {}
        )

        raw_steps = document.get("steps")
        if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, (str, bytes, bytearray)):
            issues.append("$.steps must be an array")
            raw_steps = []
        elif not raw_steps:
            issues.append("$.steps must contain at least one step")
        elif len(raw_steps) > MAX_WORKFLOW_STEPS:
            issues.append(f"$.steps must contain at most {MAX_WORKFLOW_STEPS} steps")
            raw_steps = []

        steps: list[Step] = []
        seen_ids: set[str] = set()
        for index, raw_step in enumerate(raw_steps):
            path = f"$.steps[{index}]"
            if not isinstance(raw_step, Mapping):
                issues.append(f"{path} must be an object")
                continue
            _reject_unknown_keys(raw_step, {"id", "uses", "with"}, path, issues)

            step_id = raw_step.get("id")
            if not isinstance(step_id, str) or not STEP_ID_PATTERN.fullmatch(step_id):
                issues.append(f"{path}.id must match {STEP_ID_PATTERN.pattern!r}")
                step_id = f"invalid_{index}"
            elif step_id in seen_ids:
                issues.append(f"{path}.id duplicates step id {step_id!r}")
            seen_ids.add(step_id)

            uses = raw_step.get("uses")
            if not isinstance(uses, str) or uses not in SUPPORTED_OPERATIONS:
                choices = ", ".join(sorted(SUPPORTED_OPERATIONS))
                issues.append(f"{path}.uses must be one of: {choices}")
                uses = "set"

            raw_arguments = raw_step.get("with")
            if not isinstance(raw_arguments, Mapping):
                issues.append(f"{path}.with must be an object")
                raw_arguments = {}
            argument_issue_count = len(issues)
            _validate_json_value(raw_arguments, f"{path}.with", issues)
            arguments = (
                cast(dict[str, JsonValue], _copy_json_value(raw_arguments))
                if len(issues) == argument_issue_count
                else {}
            )

            if uses == "assert":
                _validate_assert(arguments, path, issues)
            elif uses == "merge":
                _validate_merge(arguments, path, issues)
            elif uses == "pick":
                _validate_pick(arguments, path, issues)
            _validate_templates(arguments, f"{path}.with", seen_ids - {step_id}, defaults, issues)
            steps.append(Step(id=step_id, uses=uses, arguments=arguments))

        output_defined = "output" in document
        raw_output = document.get("output")
        output_valid = True
        if output_defined:
            output_issue_count = len(issues)
            _validate_json_value(raw_output, "$.output", issues)
            if len(issues) == output_issue_count:
                _validate_templates(raw_output, "$.output", seen_ids, defaults, issues)
            output_valid = len(issues) == output_issue_count
        output = _copy_json_value(raw_output) if output_valid else None

        if issues:
            raise WorkflowValidationError(issues)
        return cls(
            schema_version=SCHEMA_VERSION,
            name=cast(str, name).strip(),
            description=cast(str | None, description),
            defaults=defaults,
            steps=tuple(steps),
            output=output,
            output_defined=output_defined,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached JSON-compatible representation."""
        document: dict[str, JsonValue] = {
            "schema_version": self.schema_version,
            "name": self.name,
            "defaults": copy.deepcopy(self.defaults),
            "steps": [
                {"id": step.id, "uses": step.uses, "with": copy.deepcopy(step.arguments)}
                for step in self.steps
            ],
        }
        if self.description is not None:
            document["description"] = self.description
        if self.output_defined:
            document["output"] = copy.deepcopy(self.output)
        return document


def load_workflow(path: str | Path) -> Workflow:
    """Load a bounded UTF-8 JSON workflow from disk."""
    source = Path(path)
    return parse_workflow_bytes(_read_bounded(source), source=str(source))


def parse_workflow_bytes(data: bytes, *, source: str = "<memory>") -> Workflow:
    """Parse a workflow from bounded UTF-8 JSON bytes."""
    document = _decode_json(data, source=source)
    if not isinstance(document, Mapping):
        raise WorkflowValidationError(f"{source}: workflow root must be an object")
    try:
        return Workflow.from_dict(document)
    except WorkflowValidationError as error:
        raise WorkflowValidationError(f"{source}: {issue}" for issue in error.issues) from error


def load_json_object(path: str | Path) -> dict[str, JsonValue]:
    """Load a bounded JSON object for workflow input."""
    source = Path(path)
    return parse_json_object_bytes(_read_bounded(source), source=str(source))


def parse_json_object_bytes(data: bytes, *, source: str = "<memory>") -> dict[str, JsonValue]:
    """Parse and validate a bounded JSON object."""
    document = _decode_json(data, source=source)
    if not isinstance(document, Mapping):
        raise WorkflowValidationError(f"{source}: input root must be an object")
    issues: list[str] = []
    _validate_json_value(document, "$", issues)
    if issues:
        raise WorkflowValidationError(f"{source}: {issue}" for issue in issues)
    return cast(dict[str, JsonValue], _copy_json_value(document))


def validate_input_object(document: Mapping[str, object]) -> dict[str, JsonValue]:
    """Validate and detach API-provided workflow input."""
    issues: list[str] = []
    _validate_json_value(document, "$", issues)
    if issues:
        raise WorkflowValidationError(issues)
    return cast(dict[str, JsonValue], _copy_json_value(document))


def validate_json_value(value: object) -> JsonValue:
    """Validate and detach an API-provided JSON value."""
    issues: list[str] = []
    _validate_json_value(value, "$", issues)
    if issues:
        raise WorkflowValidationError(issues)
    return _copy_json_value(value)


def _copy_json_value(value: object) -> JsonValue:
    """Detach validated data into the renderer's concrete JSON container types."""
    if isinstance(value, Mapping):
        return {key: _copy_json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_json_value(child) for child in value]
    return cast(JsonValue, value)


def _read_bounded(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_DOCUMENT_BYTES + 1)
    except OSError as error:
        raise WorkflowValidationError(f"{path}: cannot read file: {error}") from error
    if len(data) > MAX_DOCUMENT_BYTES:
        raise WorkflowValidationError(
            f"{path}: document exceeds the {MAX_DOCUMENT_BYTES}-byte limit"
        )
    return data


def _decode_json(data: bytes, *, source: str) -> object:
    if len(data) > MAX_DOCUMENT_BYTES:
        raise WorkflowValidationError(
            f"{source}: document exceeds the {MAX_DOCUMENT_BYTES}-byte limit"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkflowValidationError(f"{source}: document must be UTF-8") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise WorkflowValidationError(f"{source}: invalid JSON: {error}") from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite number {value!r} is not valid")


def _reject_unknown_keys(
    value: Mapping[str, object], allowed: set[str], path: str, issues: list[str]
) -> None:
    for key in value:
        if key not in allowed:
            issues.append(f"{path} contains unknown field {key!r}")


def _validate_json_value(
    value: object,
    path: str,
    issues: list[str],
    *,
    depth: int = 0,
    ancestors: set[int] | None = None,
    budget: list[int] | None = None,
) -> None:
    remaining = [MAX_JSON_VALUES] if budget is None else budget
    if remaining[0] <= 0:
        if remaining[0] == 0:
            issues.append(f"{path} exceeds the {MAX_JSON_VALUES}-value document limit")
            remaining[0] = -1
        return
    remaining[0] -= 1
    if depth > MAX_NESTING:
        issues.append(f"{path} exceeds the maximum nesting depth of {MAX_NESTING}")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            issues.append(f"{path} must not contain a non-finite number")
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            issues.append(f"{path} exceeds the {MAX_STRING_LENGTH}-character string limit")
        return
    if not isinstance(value, (Mapping, list, tuple)):
        issues.append(f"{path} contains unsupported value type {type(value).__name__}")
        return

    active = set() if ancestors is None else ancestors
    identity = id(value)
    if identity in active:
        issues.append(f"{path} contains a reference cycle")
        return
    if len(value) > MAX_COLLECTION_ITEMS:
        issues.append(f"{path} exceeds the {MAX_COLLECTION_ITEMS}-item collection limit")
        return
    active.add(identity)
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                issues.append(f"{path} contains a non-string key")
                continue
            if len(key) > MAX_STRING_LENGTH:
                issues.append(f"{path} contains an overlong object key")
                continue
            _validate_json_value(
                child,
                f"{path}.{key}",
                issues,
                depth=depth + 1,
                ancestors=active,
                budget=remaining,
            )
    else:
        for index, child in enumerate(value):
            _validate_json_value(
                child,
                f"{path}[{index}]",
                issues,
                depth=depth + 1,
                ancestors=active,
                budget=remaining,
            )
    active.remove(identity)


def _validate_assert(arguments: dict[str, JsonValue], path: str, issues: list[str]) -> None:
    allowed = {"expected", "message", "operator", "value"}
    _reject_unknown_keys(arguments, allowed, f"{path}.with", issues)
    if "value" not in arguments:
        issues.append(f"{path}.with.value is required for assert")
    operator = arguments.get("operator")
    if not isinstance(operator, str) or operator not in ASSERT_OPERATORS:
        choices = ", ".join(sorted(ASSERT_OPERATORS))
        issues.append(f"{path}.with.operator must be one of: {choices}")
    elif (
        operator
        in {
            "contains",
            "equals",
            "greater_or_equal",
            "greater_than",
            "less_or_equal",
            "less_than",
            "not_equals",
        }
        and "expected" not in arguments
    ):
        issues.append(f"{path}.with.expected is required for operator {operator!r}")
    message = arguments.get("message")
    if message is not None and not isinstance(message, str):
        issues.append(f"{path}.with.message must be a string")


def _validate_merge(arguments: dict[str, JsonValue], path: str, issues: list[str]) -> None:
    _reject_unknown_keys(arguments, {"objects"}, f"{path}.with", issues)
    if "objects" not in arguments:
        issues.append(f"{path}.with.objects is required for merge")
        return
    objects = arguments["objects"]
    if isinstance(objects, str) and TEMPLATE_PATTERN.fullmatch(objects):
        return
    if not isinstance(objects, list):
        issues.append(f"{path}.with.objects must be an array or exact template")
        return
    for index, value in enumerate(objects):
        if isinstance(value, dict):
            continue
        if isinstance(value, str) and TEMPLATE_PATTERN.fullmatch(value):
            continue
        issues.append(f"{path}.with.objects[{index}] must be an object or exact template")


def _validate_pick(arguments: dict[str, JsonValue], path: str, issues: list[str]) -> None:
    _reject_unknown_keys(arguments, {"keys", "object", "required"}, f"{path}.with", issues)
    if "object" not in arguments:
        issues.append(f"{path}.with.object is required for pick")
    else:
        value = arguments["object"]
        if not isinstance(value, dict) and not (
            isinstance(value, str) and TEMPLATE_PATTERN.fullmatch(value)
        ):
            issues.append(f"{path}.with.object must be an object or exact template")
    if "keys" not in arguments:
        issues.append(f"{path}.with.keys is required for pick")
    else:
        keys = arguments["keys"]
        if isinstance(keys, str) and TEMPLATE_PATTERN.fullmatch(keys):
            pass
        elif not isinstance(keys, list):
            issues.append(f"{path}.with.keys must be an array or exact template")
        else:
            for index, key in enumerate(keys):
                if not isinstance(key, str):
                    issues.append(f"{path}.with.keys[{index}] must be a string")
    required = arguments.get("required")
    if required is not None and not isinstance(required, (bool, str)):
        issues.append(f"{path}.with.required must be a boolean or template")
    elif isinstance(required, str) and not TEMPLATE_PATTERN.fullmatch(required):
        issues.append(f"{path}.with.required must be a boolean or exact template")


def _validate_templates(
    value: object,
    path: str,
    available_steps: set[str],
    defaults: Mapping[str, JsonValue],
    issues: list[str],
) -> None:
    if isinstance(value, str):
        remainder = TEMPLATE_PATTERN.sub("", value)
        if "{{" in remainder or "}}" in remainder:
            issues.append(f"{path} contains malformed template syntax")
        for match in TEMPLATE_PATTERN.finditer(value):
            segments = match.group(1).split(".")
            root = segments[0]
            if root not in {"defaults", "input", "steps"}:
                issues.append(f"{path} uses unsupported template root {root!r}")
            elif root == "steps":
                if len(segments) < 2:
                    issues.append(f"{path} must name a step after 'steps'")
                elif segments[1] not in available_steps:
                    issues.append(f"{path} references step {segments[1]!r} before it is available")
            elif root == "defaults" and len(segments) > 1 and segments[1] not in defaults:
                issues.append(f"{path} references missing default {segments[1]!r}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            _validate_templates(child, f"{path}.{key}", available_steps, defaults, issues)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_templates(child, f"{path}[{index}]", available_steps, defaults, issues)
