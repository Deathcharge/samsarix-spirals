# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Static, value-free workflow explanations."""

from __future__ import annotations

from dataclasses import dataclass

from .model import TEMPLATE_PATTERN, JsonValue, Workflow


@dataclass(frozen=True, slots=True)
class StepExplanation:
    """Direct references made by one workflow step."""

    id: str
    uses: str
    depends_on: tuple[str, ...]
    input_paths: tuple[str, ...]
    default_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached JSON-compatible representation."""
        return {
            "id": self.id,
            "uses": self.uses,
            "depends_on": list(self.depends_on),
            "input_paths": list(self.input_paths),
            "default_paths": list(self.default_paths),
        }


@dataclass(frozen=True, slots=True)
class OutputExplanation:
    """Direct references used to produce the workflow output."""

    depends_on: tuple[str, ...]
    input_paths: tuple[str, ...]
    default_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached JSON-compatible representation."""
        return {
            "depends_on": list(self.depends_on),
            "input_paths": list(self.input_paths),
            "default_paths": list(self.default_paths),
        }


@dataclass(frozen=True, slots=True)
class WorkflowExplanation:
    """A deterministic static summary of a validated workflow."""

    workflow: str
    steps: tuple[StepExplanation, ...]
    output: OutputExplanation
    input_paths: tuple[str, ...]
    default_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached JSON-compatible representation."""
        return {
            "explain_version": 1,
            "workflow": self.workflow,
            "input_paths": list(self.input_paths),
            "default_paths": list(self.default_paths),
            "steps": [step.to_dict() for step in self.steps],
            "output": self.output.to_dict(),
        }


def explain_workflow(workflow: Workflow) -> WorkflowExplanation:
    """Describe direct data references without executing *workflow*."""
    steps: list[StepExplanation] = []
    all_inputs: set[str] = set()
    all_defaults: set[str] = set()

    for step in workflow.steps:
        references = _collect_references(step.arguments)
        all_inputs.update(references.input_paths)
        all_defaults.update(references.default_paths)
        steps.append(
            StepExplanation(
                id=step.id,
                uses=step.uses,
                depends_on=references.depends_on,
                input_paths=references.input_paths,
                default_paths=references.default_paths,
            )
        )

    if workflow.output_defined:
        output = _collect_references(workflow.output)
    else:
        output = OutputExplanation(
            depends_on=(workflow.steps[-1].id,),
            input_paths=(),
            default_paths=(),
        )
    all_inputs.update(output.input_paths)
    all_defaults.update(output.default_paths)

    return WorkflowExplanation(
        workflow=workflow.name,
        steps=tuple(steps),
        output=output,
        input_paths=tuple(sorted(all_inputs)),
        default_paths=tuple(sorted(all_defaults)),
    )


def _collect_references(value: JsonValue) -> OutputExplanation:
    dependencies: set[str] = set()
    inputs: set[str] = set()
    defaults: set[str] = set()

    def visit(child: JsonValue) -> None:
        if isinstance(child, str):
            for match in TEMPLATE_PATTERN.finditer(child):
                reference = match.group(1)
                root, *segments = reference.split(".")
                if root == "input":
                    inputs.add(reference)
                elif root == "defaults":
                    defaults.add(reference)
                elif root == "steps":
                    dependencies.add(segments[0])
        elif isinstance(child, list):
            for item in child:
                visit(item)
        elif isinstance(child, dict):
            for item in child.values():
                visit(item)

    visit(value)
    return OutputExplanation(
        depends_on=tuple(sorted(dependencies)),
        input_paths=tuple(sorted(inputs)),
        default_paths=tuple(sorted(defaults)),
    )
