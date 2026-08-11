# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
from __future__ import annotations

from pathlib import Path

import pytest

from samsarix_spirals import load_suite, load_workflow, run_suite

EXAMPLES = Path(__file__).parents[1] / "examples"
SUITES = sorted(EXAMPLES.glob("*.suite.json"))


@pytest.mark.parametrize("suite_path", SUITES, ids=lambda path: path.name)
def test_checked_in_example_suite_passes(suite_path: Path) -> None:
    workflow_path = suite_path.with_name(suite_path.name.removesuffix(".suite.json") + ".json")

    result = run_suite(load_workflow(workflow_path), load_suite(suite_path))

    failures = [f"{case.name}: {case.detail}" for case in result.cases if not case.passed]
    assert result.successful, failures
