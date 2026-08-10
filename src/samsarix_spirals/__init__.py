# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Samsarix Spirals public API."""

from .errors import SamsarixSpiralsError, WorkflowExecutionError, WorkflowValidationError
from .model import Step, Workflow, load_workflow
from .runner import RunResult, StepResult, run_workflow
from .suite import SuiteResult, WorkflowSuite, load_suite, run_suite

__version__ = "0.1.0"

__all__ = [
    "RunResult",
    "SamsarixSpiralsError",
    "Step",
    "StepResult",
    "SuiteResult",
    "Workflow",
    "WorkflowExecutionError",
    "WorkflowSuite",
    "WorkflowValidationError",
    "load_suite",
    "load_workflow",
    "run_suite",
    "run_workflow",
]
