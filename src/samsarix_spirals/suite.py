# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Bounded regression suites for deterministic workflow contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .errors import WorkflowExecutionError, WorkflowValidationError
from .model import JsonValue, Workflow, load_json_object, validate_input_object, validate_json_value
from .runner import run_workflow

SUITE_VERSION = 1
MAX_SUITE_CASES = 1_000
MAX_CASE_NAME_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ErrorExpectation:
    """Expected execution-error details for a regression case."""

    step_id: str | None = None
    message_contains: str | None = None


@dataclass(frozen=True, slots=True)
class SuiteCase:
    """One named input and its expected workflow outcome."""

    name: str
    input: dict[str, JsonValue]
    expected_output: JsonValue
    expected_error: ErrorExpectation | None
    expects_output: bool


@dataclass(frozen=True, slots=True)
class WorkflowSuite:
    """A validated version 1 workflow regression suite."""

    suite_version: int
    name: str
    cases: tuple[SuiteCase, ...]

    @classmethod
    def from_dict(cls, document: Mapping[str, object]) -> WorkflowSuite:
        """Validate and detach a regression-suite mapping."""
        issues: list[str] = []
        _reject_unknown_keys(document, {"suite_version", "name", "cases"}, "$", issues)

        suite_version = document.get("suite_version")
        if suite_version != SUITE_VERSION or isinstance(suite_version, bool):
            issues.append(f"$.suite_version must be the integer {SUITE_VERSION}")

        name = document.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append("$.name must be a non-empty string")
        elif len(name) > 100:
            issues.append("$.name must contain at most 100 characters")

        raw_cases = document.get("cases")
        if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes, bytearray)):
            issues.append("$.cases must be an array")
            raw_cases = []
        elif not raw_cases:
            issues.append("$.cases must contain at least one case")
        elif len(raw_cases) > MAX_SUITE_CASES:
            issues.append(f"$.cases must contain at most {MAX_SUITE_CASES} cases")
            raw_cases = []

        cases: list[SuiteCase] = []
        seen_names: set[str] = set()
        for index, raw_case in enumerate(raw_cases):
            path = f"$.cases[{index}]"
            if not isinstance(raw_case, Mapping):
                issues.append(f"{path} must be an object")
                continue
            _reject_unknown_keys(raw_case, {"name", "input", "expect"}, path, issues)

            case_name = raw_case.get("name")
            if not isinstance(case_name, str) or not case_name.strip():
                issues.append(f"{path}.name must be a non-empty string")
                normalized_name = f"invalid-{index}"
            else:
                normalized_name = case_name.strip()
                if len(normalized_name) > MAX_CASE_NAME_LENGTH:
                    issues.append(
                        f"{path}.name must contain at most {MAX_CASE_NAME_LENGTH} characters"
                    )
                if normalized_name in seen_names:
                    issues.append(f"{path}.name duplicates case name {normalized_name!r}")
            seen_names.add(normalized_name)

            raw_input = raw_case.get("input", {})
            if not isinstance(raw_input, Mapping):
                issues.append(f"{path}.input must be an object")
                case_input: dict[str, JsonValue] = {}
            else:
                try:
                    case_input = validate_input_object(raw_input)
                except WorkflowValidationError as error:
                    issues.extend(f"{path}.input: {issue}" for issue in error.issues)
                    case_input = {}

            raw_expect = raw_case.get("expect")
            if not isinstance(raw_expect, Mapping):
                issues.append(f"{path}.expect must be an object")
                raw_expect = {}
            _reject_unknown_keys(raw_expect, {"output", "error"}, f"{path}.expect", issues)
            expects_output = "output" in raw_expect
            expects_error = "error" in raw_expect
            if expects_output == expects_error:
                issues.append(f"{path}.expect must contain exactly one of 'output' or 'error'")

            expected_output: JsonValue = None
            if expects_output:
                try:
                    expected_output = validate_json_value(raw_expect.get("output"))
                except WorkflowValidationError as error:
                    issues.extend(f"{path}.expect.output: {issue}" for issue in error.issues)

            expected_error: ErrorExpectation | None = None
            if expects_error:
                raw_error = raw_expect.get("error")
                if not isinstance(raw_error, Mapping):
                    issues.append(f"{path}.expect.error must be an object")
                else:
                    _reject_unknown_keys(
                        raw_error,
                        {"step_id", "message_contains"},
                        f"{path}.expect.error",
                        issues,
                    )
                    step_id = raw_error.get("step_id")
                    message_contains = raw_error.get("message_contains")
                    if step_id is not None and (not isinstance(step_id, str) or not step_id):
                        issues.append(f"{path}.expect.error.step_id must be a non-empty string")
                    if message_contains is not None and (
                        not isinstance(message_contains, str) or not message_contains
                    ):
                        issues.append(
                            f"{path}.expect.error.message_contains must be a non-empty string"
                        )
                    expected_error = ErrorExpectation(
                        step_id=step_id if isinstance(step_id, str) else None,
                        message_contains=(
                            message_contains if isinstance(message_contains, str) else None
                        ),
                    )

            cases.append(
                SuiteCase(
                    name=normalized_name,
                    input=case_input,
                    expected_output=expected_output,
                    expected_error=expected_error,
                    expects_output=expects_output,
                )
            )

        if issues:
            raise WorkflowValidationError(issues)
        return cls(
            suite_version=SUITE_VERSION,
            name=cast(str, name).strip(),
            cases=tuple(cases),
        )


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The non-sensitive result of one regression case."""

    name: str
    passed: bool
    detail: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {"name": self.name, "passed": self.passed}
        if self.detail is not None:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """Aggregate result of a complete regression suite."""

    suite: str
    cases: tuple[CaseResult, ...]

    @property
    def passed(self) -> int:
        return sum(case.passed for case in self.cases)

    @property
    def failed(self) -> int:
        return len(self.cases) - self.passed

    @property
    def successful(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "suite": self.suite,
            "successful": self.successful,
            "passed": self.passed,
            "failed": self.failed,
            "cases": [case.to_dict() for case in self.cases],
        }


def load_suite(path: str | Path) -> WorkflowSuite:
    """Load a bounded regression suite from disk."""
    source = Path(path)
    document = load_json_object(source)
    try:
        return WorkflowSuite.from_dict(document)
    except WorkflowValidationError as error:
        raise WorkflowValidationError(f"{source}: {issue}" for issue in error.issues) from error


def run_suite(workflow: Workflow, suite: WorkflowSuite) -> SuiteResult:
    """Run every suite case without stopping at the first failed expectation."""
    return SuiteResult(
        suite=suite.name,
        cases=tuple(_run_case(workflow, case) for case in suite.cases),
    )


def _run_case(workflow: Workflow, case: SuiteCase) -> CaseResult:
    try:
        result = run_workflow(workflow, case.input)
    except WorkflowExecutionError as error:
        if case.expects_output:
            return CaseResult(case.name, False, "workflow failed but output was expected")
        expectation = case.expected_error
        if expectation is None:  # pragma: no cover - validated suite invariant
            return CaseResult(case.name, False, "invalid error expectation")
        if expectation.step_id is not None and error.step_id != expectation.step_id:
            return CaseResult(case.name, False, "execution failed at an unexpected step")
        if expectation.message_contains is not None and expectation.message_contains not in str(
            error
        ):
            return CaseResult(case.name, False, "execution error did not contain expected text")
        return CaseResult(case.name, True)

    if not case.expects_output:
        return CaseResult(
            case.name, False, "workflow completed but an execution error was expected"
        )
    if result.output != case.expected_output:
        return CaseResult(case.name, False, "workflow output did not equal expected output")
    return CaseResult(case.name, True)


def _reject_unknown_keys(
    value: Mapping[str, object], allowed: set[str], path: str, issues: list[str]
) -> None:
    for key in value:
        if key not in allowed:
            issues.append(f"{path} contains unknown field {key!r}")
