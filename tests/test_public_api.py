# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

import samsarix_spirals


def test_public_api_is_small_and_versioned() -> None:
    assert samsarix_spirals.__version__ == "0.1.0"
    assert set(samsarix_spirals.__all__) == {
        "SamsarixSpiralsError",
        "RunResult",
        "Step",
        "StepResult",
        "Workflow",
        "WorkflowExecutionError",
        "WorkflowValidationError",
        "load_workflow",
        "run_workflow",
    }
