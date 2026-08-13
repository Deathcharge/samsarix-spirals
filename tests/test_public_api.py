# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import samsarix_spirals


def test_public_api_is_small_and_versioned() -> None:
    assert samsarix_spirals.__version__ == "0.1.0"
    assert set(samsarix_spirals.__all__) == {
        "SamsarixSpiralsError",
        "RunResult",
        "OutputExplanation",
        "Step",
        "StepExplanation",
        "StepResult",
        "SuiteResult",
        "Workflow",
        "WorkflowExplanation",
        "WorkflowExecutionError",
        "WorkflowValidationError",
        "WorkflowSuite",
        "get_schema",
        "explain_workflow",
        "load_suite",
        "load_workflow",
        "run_workflow",
        "run_suite",
        "suite_result_to_junit_xml",
    }
