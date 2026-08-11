# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Bundled JSON Schema discovery."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Literal, cast

from .model import JsonValue

SchemaName = Literal["suite", "workflow"]
SCHEMA_NAMES: tuple[SchemaName, ...] = ("suite", "workflow")
_SCHEMA_FILES: dict[SchemaName, str] = {
    "suite": "suite-v1.schema.json",
    "workflow": "workflow-v1.schema.json",
}


def get_schema(name: SchemaName) -> dict[str, JsonValue]:
    """Return a detached bundled Draft 2020-12 schema."""
    resource = files("samsarix_spirals").joinpath("schemas", _SCHEMA_FILES[name])
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict):  # pragma: no cover - packaged resource invariant
        raise RuntimeError(f"bundled {name} schema root is not an object")
    return cast(dict[str, JsonValue], document)
