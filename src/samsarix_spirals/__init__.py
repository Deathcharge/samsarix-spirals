# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Samsarix Spirals public API."""

from .errors import SamsarixSpiralsError, WorkflowExecutionError, WorkflowValidationError
from .explain import OutputExplanation, StepExplanation, WorkflowExplanation, explain_workflow
from .model import Step, Workflow, load_workflow
from .runner import RunResult, StepResult, run_workflow
from .schema import get_schema
from .suite import SuiteResult, WorkflowSuite, load_suite, run_suite, suite_result_to_junit_xml

__version__ = "0.1.0"

__all__ = [
    "OutputExplanation",
    "RunResult",
    "SamsarixSpiralsError",
    "Step",
    "StepExplanation",
    "StepResult",
    "SuiteResult",
    "Workflow",
    "WorkflowExecutionError",
    "WorkflowExplanation",
    "WorkflowSuite",
    "WorkflowValidationError",
    "explain_workflow",
    "get_schema",
    "load_suite",
    "load_workflow",
    "run_suite",
    "run_workflow",
    "suite_result_to_junit_xml",
]
