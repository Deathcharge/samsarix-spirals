# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Shared JSON value semantics for execution and contract testing."""

from __future__ import annotations

from .model import JsonValue


def json_equal(actual: JsonValue, expected: JsonValue) -> bool:
    """Compare validated JSON values without Python's boolean/number coercion."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected, strict=True)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_equal(actual[key], expected[key]) for key in actual
        )
    return actual == expected
