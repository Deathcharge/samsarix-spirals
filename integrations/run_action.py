# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Bootstrap only the action's pinned source, never the consumer's Python package."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Invoked using Python -I: cwd, PYTHONPATH, and user-site packages cannot shadow imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from samsarix_spirals.ci import main

if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "--github-annotations",
                "--workspace",
                os.environ.get("GITHUB_WORKSPACE", str(Path.cwd())),
                "--",
                os.environ.get("SAMSARIX_WORKFLOW", ""),
                os.environ.get("SAMSARIX_SUITE", ""),
            ]
        )
    )
