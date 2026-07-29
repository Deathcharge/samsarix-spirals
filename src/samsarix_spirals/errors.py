# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Public exceptions for Samsarix Spirals."""

from __future__ import annotations

from collections.abc import Iterable


class SamsarixSpiralsError(Exception):
    """Base class for expected Samsarix Spirals errors."""


class WorkflowValidationError(SamsarixSpiralsError, ValueError):
    """Raised when a workflow or input document is invalid."""

    def __init__(self, issues: str | Iterable[str]) -> None:
        normalized: tuple[str, ...] = (issues,) if isinstance(issues, str) else tuple(issues)
        if not normalized:
            normalized = ("validation failed",)
        self.issues = normalized
        super().__init__("; ".join(normalized))


class WorkflowExecutionError(SamsarixSpiralsError, RuntimeError):
    """Raised when a valid workflow cannot complete."""

    def __init__(self, message: str, *, step_id: str | None = None) -> None:
        self.step_id = step_id
        prefix = f"step {step_id!r}: " if step_id else ""
        super().__init__(f"{prefix}{message}")
