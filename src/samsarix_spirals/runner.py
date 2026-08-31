# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Deterministic, side-effect-free workflow execution."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from ._json import json_equal
from .errors import WorkflowExecutionError
from .model import (
    DEFAULT_MAX_RUN_STEPS,
    MAX_COLLECTION_ITEMS,
    MAX_JSON_VALUES,
    MAX_NESTING,
    MAX_STRING_LENGTH,
    MAX_WORKFLOW_STEPS,
    TEMPLATE_PATTERN,
    JsonValue,
    Step,
    Workflow,
    validate_input_object,
)

MAX_RENDERED_BYTES = 4 * 1_048_576
MAX_RUN_OUTPUT_BYTES = 16 * 1_048_576
_SIZE_ENCODER = json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(",", ":"))


@dataclass(slots=True)
class _RenderBudget:
    remaining_values: int = MAX_JSON_VALUES
    remaining_bytes: int = field(default_factory=lambda: MAX_RENDERED_BYTES)


@dataclass(frozen=True, slots=True)
class StepResult:
    """The observable result of one completed step."""

    id: str
    operation: str
    output: JsonValue

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "operation": self.operation,
            "status": "completed",
            "output": copy.deepcopy(self.output),
        }


@dataclass(frozen=True, slots=True)
class RunResult:
    """A deterministic workflow result."""

    workflow: str
    output: JsonValue
    steps: tuple[StepResult, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": "completed",
            "workflow": self.workflow,
            "output": copy.deepcopy(self.output),
            "steps": [step.to_dict() for step in self.steps],
        }


def run_workflow(
    workflow: Workflow,
    input_data: Mapping[str, object] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_RUN_STEPS,
) -> RunResult:
    """Run a validated workflow without network, process, or file side effects."""
    if isinstance(max_steps, bool) or not 1 <= max_steps <= MAX_WORKFLOW_STEPS:
        raise WorkflowExecutionError(f"max_steps must be between 1 and {MAX_WORKFLOW_STEPS}")
    if len(workflow.steps) > max_steps:
        raise WorkflowExecutionError(
            f"workflow has {len(workflow.steps)} steps, exceeding the run limit of {max_steps}"
        )

    safe_input = validate_input_object(input_data or {})
    context: dict[str, JsonValue] = {
        "input": safe_input,
        "defaults": copy.deepcopy(workflow.defaults),
        "steps": {},
    }
    results: list[StepResult] = []
    step_outputs: dict[str, JsonValue] = {}
    context["steps"] = step_outputs
    remaining_output_bytes = MAX_RUN_OUTPUT_BYTES

    for step in workflow.steps:
        rendered = _render(step.arguments, context, step_id=step.id)
        if not isinstance(rendered, dict):  # pragma: no cover - validated model invariant
            raise WorkflowExecutionError(
                "step arguments did not render to an object", step_id=step.id
            )
        output = _execute_step(step, rendered)
        remaining_output_bytes = _consume_output_bytes(
            output, remaining_output_bytes, step_id=step.id
        )
        step_outputs[step.id] = copy.deepcopy(output)
        results.append(StepResult(id=step.id, operation=step.uses, output=output))

    if workflow.output_defined:
        final_output = _render(workflow.output, context)
    else:
        final_output = copy.deepcopy(results[-1].output)
    _consume_output_bytes(final_output, remaining_output_bytes, step_id=None)
    return RunResult(workflow=workflow.name, output=final_output, steps=tuple(results))


def _execute_step(step: Step, arguments: dict[str, JsonValue]) -> JsonValue:
    if step.uses == "set":
        return copy.deepcopy(arguments)
    if step.uses == "merge":
        return _merge_objects(arguments, step_id=step.id)
    if step.uses == "pick":
        return _pick_keys(arguments, step_id=step.id)
    if step.uses == "assert":
        value = arguments.get("value")
        expected = arguments.get("expected")
        operator = arguments.get("operator")
        if not isinstance(operator, str):  # pragma: no cover - validated model invariant
            raise WorkflowExecutionError(
                "assert operator did not render to a string", step_id=step.id
            )
        try:
            passed = _evaluate_assertion(value, operator, expected)
        except TypeError as error:
            raise WorkflowExecutionError(str(error), step_id=step.id) from error
        if not passed:
            message = arguments.get("message")
            detail = (
                message
                if isinstance(message, str) and message
                else f"assertion {operator!r} failed"
            )
            raise WorkflowExecutionError(detail, step_id=step.id)
        return {"passed": True, "value": copy.deepcopy(value)}
    raise WorkflowExecutionError(  # pragma: no cover - validated model invariant
        f"unsupported operation {step.uses!r}", step_id=step.id
    )


def _merge_objects(arguments: dict[str, JsonValue], *, step_id: str) -> JsonValue:
    objects = arguments.get("objects")
    if not isinstance(objects, list):
        raise WorkflowExecutionError("merge objects must render to an array", step_id=step_id)
    merged: dict[str, JsonValue] = {}
    for index, value in enumerate(objects):
        if not isinstance(value, dict):
            raise WorkflowExecutionError(
                f"merge objects[{index}] must render to an object", step_id=step_id
            )
        merged.update(copy.deepcopy(value))
        if len(merged) > MAX_COLLECTION_ITEMS:
            raise WorkflowExecutionError(
                f"merged object exceeds the {MAX_COLLECTION_ITEMS}-key limit", step_id=step_id
            )
    return merged


def _pick_keys(arguments: dict[str, JsonValue], *, step_id: str) -> JsonValue:
    value = arguments.get("object")
    keys = arguments.get("keys")
    required = arguments.get("required", True)
    if not isinstance(value, dict):
        raise WorkflowExecutionError("pick object must render to an object", step_id=step_id)
    if not isinstance(keys, list):
        raise WorkflowExecutionError("pick keys must render to an array", step_id=step_id)
    if not isinstance(required, bool):
        raise WorkflowExecutionError("pick required must render to a boolean", step_id=step_id)

    selected: dict[str, JsonValue] = {}
    seen: set[str] = set()
    for index, key in enumerate(keys):
        if not isinstance(key, str):
            raise WorkflowExecutionError(
                f"pick keys[{index}] must render to a string", step_id=step_id
            )
        if key in seen:
            raise WorkflowExecutionError(f"pick key {key!r} is duplicated", step_id=step_id)
        seen.add(key)
        if key not in value:
            if required:
                raise WorkflowExecutionError(
                    f"pick object is missing required key {key!r}", step_id=step_id
                )
            continue
        selected[key] = copy.deepcopy(value[key])
    return selected


def _evaluate_assertion(value: JsonValue, operator: str, expected: JsonValue) -> bool:
    if operator == "equals":
        return json_equal(value, expected)
    if operator == "not_equals":
        return not json_equal(value, expected)
    if operator == "truthy":
        return bool(value)
    if operator == "falsy":
        return not value
    if operator == "not_empty":
        return value is not None and value != "" and value != [] and value != {}
    if operator == "contains":
        if isinstance(value, str):
            if not isinstance(expected, str):
                raise TypeError("contains on a string requires a string expected value")
            return expected in value
        if isinstance(value, list):
            return any(json_equal(item, expected) for item in value)
        if isinstance(value, dict):
            if not isinstance(expected, str):
                raise TypeError("contains on an object requires a string expected key")
            return expected in value
        raise TypeError("contains requires a string, array, or object value")
    if operator in {"greater_than", "greater_or_equal", "less_than", "less_or_equal"}:
        if isinstance(value, bool) or isinstance(expected, bool):
            raise TypeError(f"{operator} does not compare booleans")
        if isinstance(value, str) and isinstance(expected, str):
            if operator == "greater_than":
                return value > expected
            if operator == "greater_or_equal":
                return value >= expected
            if operator == "less_than":
                return value < expected
            return value <= expected
        if isinstance(value, (int, float)) and isinstance(expected, (int, float)):
            if operator == "greater_than":
                return value > expected
            if operator == "greater_or_equal":
                return value >= expected
            if operator == "less_than":
                return value < expected
            return value <= expected
        raise TypeError(f"{operator} requires values of the same numeric or string type")
    raise TypeError(f"unsupported assert operator {operator!r}")  # pragma: no cover


def _render(
    value: JsonValue,
    context: Mapping[str, JsonValue],
    *,
    step_id: str | None = None,
    budget: _RenderBudget | None = None,
    depth: int = 0,
) -> JsonValue:
    active_budget = _RenderBudget() if budget is None else budget
    if depth > MAX_NESTING:
        raise WorkflowExecutionError("rendered value exceeds the nesting limit", step_id=step_id)
    if isinstance(value, str):
        exact = TEMPLATE_PATTERN.fullmatch(value)
        if exact:
            return _clone_with_budget(
                _resolve(exact.group(1), context, step_id=step_id),
                active_budget,
                step_id=step_id,
                depth=depth,
            )

        literal_characters = len(TEMPLATE_PATTERN.sub("", value))

        def replace(match: re.Match[str]) -> str:
            nonlocal literal_characters
            resolved = _resolve(match.group(1), context, step_id=step_id)
            if isinstance(resolved, (dict, list)):
                raise WorkflowExecutionError(
                    "objects and arrays require an exact template placeholder",
                    step_id=step_id,
                )
            if resolved is None:
                return "null"
            if isinstance(resolved, bool):
                replacement = "true" if resolved else "false"
            else:
                try:
                    replacement = str(resolved)
                except ValueError as error:
                    raise WorkflowExecutionError(
                        "rendered scalar cannot be encoded as JSON", step_id=step_id
                    ) from error
            literal_characters += len(replacement)
            if literal_characters > MAX_STRING_LENGTH:
                raise WorkflowExecutionError(
                    f"rendered string exceeds {MAX_STRING_LENGTH} characters",
                    step_id=step_id,
                )
            return replacement

        rendered = TEMPLATE_PATTERN.sub(replace, value)
        if len(rendered) > MAX_STRING_LENGTH:
            raise WorkflowExecutionError(
                f"rendered string exceeds {MAX_STRING_LENGTH} characters",
                step_id=step_id,
            )
        _consume_value(active_budget, rendered, step_id=step_id)
        return rendered
    if isinstance(value, list):
        _consume_value(active_budget, value, step_id=step_id)
        return [
            _render(child, context, step_id=step_id, budget=active_budget, depth=depth + 1)
            for child in value
        ]
    if isinstance(value, dict):
        _consume_value(active_budget, value, step_id=step_id)
        return {
            key: _render(child, context, step_id=step_id, budget=active_budget, depth=depth + 1)
            for key, child in value.items()
        }
    _consume_value(active_budget, value, step_id=step_id)
    return value


def _clone_with_budget(
    value: JsonValue,
    budget: _RenderBudget,
    *,
    step_id: str | None,
    depth: int = 0,
) -> JsonValue:
    _consume_value(budget, value, step_id=step_id)
    if depth > MAX_NESTING:
        raise WorkflowExecutionError("rendered value exceeds the nesting limit", step_id=step_id)
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:  # pragma: no cover - validated context invariant
            raise WorkflowExecutionError(
                "rendered string exceeds the character limit", step_id=step_id
            )
        return value
    if isinstance(value, list):
        if len(value) > MAX_COLLECTION_ITEMS:  # pragma: no cover - validated context invariant
            raise WorkflowExecutionError("rendered array exceeds the item limit", step_id=step_id)
        return [
            _clone_with_budget(child, budget, step_id=step_id, depth=depth + 1) for child in value
        ]
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION_ITEMS:  # pragma: no cover - validated context invariant
            raise WorkflowExecutionError("rendered object exceeds the item limit", step_id=step_id)
        return {
            key: _clone_with_budget(child, budget, step_id=step_id, depth=depth + 1)
            for key, child in value.items()
        }
    return value


def _consume_value(budget: _RenderBudget, value: JsonValue, *, step_id: str | None) -> None:
    if budget.remaining_values <= 0:
        raise WorkflowExecutionError(
            f"rendered value exceeds the {MAX_JSON_VALUES}-value limit",
            step_id=step_id,
        )
    budget.remaining_values -= 1
    # Count compact ASCII-escaped JSON without constructing the whole encoded tree.
    # Strings/keys are already character-bounded by validation/rendering.
    if isinstance(value, (list, dict)):
        _consume_render_bytes(budget, 2 + max(0, len(value) - 1), step_id=step_id)
        if isinstance(value, dict):
            for key in value:
                _consume_render_bytes(budget, len(_SIZE_ENCODER.encode(key)) + 1, step_id=step_id)
    else:
        try:
            size = len(_SIZE_ENCODER.encode(value))
        except ValueError as error:
            raise WorkflowExecutionError(
                "rendered scalar cannot be encoded as JSON", step_id=step_id
            ) from error
        _consume_render_bytes(budget, size, step_id=step_id)


def _consume_render_bytes(budget: _RenderBudget, size: int, *, step_id: str | None) -> None:
    if size > budget.remaining_bytes:
        raise WorkflowExecutionError(
            f"rendered value exceeds the {MAX_RENDERED_BYTES}-byte limit", step_id=step_id
        )
    budget.remaining_bytes -= size


def _consume_output_bytes(value: JsonValue, remaining: int, *, step_id: str | None) -> int:
    # Iterate fragments rather than allocating another full serialized output. Repeated
    # references count each time, including the final output's copy of the last step.
    for fragment in _SIZE_ENCODER.iterencode(value):
        remaining -= len(fragment)
        if remaining < 0:
            raise WorkflowExecutionError(
                f"combined output exceeds the {MAX_RUN_OUTPUT_BYTES}-byte limit", step_id=step_id
            )
    return remaining


def _resolve(reference: str, context: Mapping[str, JsonValue], *, step_id: str | None) -> JsonValue:
    segments = reference.split(".")
    current: JsonValue = context.get(segments[0])
    if segments[0] not in context:  # pragma: no cover - validated model invariant
        raise WorkflowExecutionError(f"unknown template root {segments[0]!r}", step_id=step_id)
    for segment in segments[1:]:
        if isinstance(current, dict):
            if segment not in current:
                raise WorkflowExecutionError(
                    f"template reference {reference!r} is missing {segment!r}",
                    step_id=step_id,
                )
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            if len(segment) > 10:
                raise WorkflowExecutionError(
                    f"template reference {reference!r} has an oversized array index",
                    step_id=step_id,
                )
            index = int(segment)
            if index >= len(current):
                raise WorkflowExecutionError(
                    f"template reference {reference!r} has an out-of-range index",
                    step_id=step_id,
                )
            current = current[index]
        else:
            raise WorkflowExecutionError(
                f"template reference {reference!r} cannot traverse {segment!r}",
                step_id=step_id,
            )
    return current
