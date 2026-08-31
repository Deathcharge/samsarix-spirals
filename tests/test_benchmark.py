# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Validate the measurement harness and outcomes, never machine-speed thresholds."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/benchmark.py"
spec = importlib.util.spec_from_file_location("spirals_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def call(*args):
    return subprocess.run(  # noqa: S603 - fixed local script and test arguments
        [sys.executable, "-I", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize("scenario", benchmark.SCENARIOS)
def test_fresh_worker_checks_each_scenario(scenario):
    result = call("--worker", scenario)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["elapsed_ns"] > 0
    assert report["setup_ns"] > 0
    assert report["units"] >= 1
    if sys.platform in {"win32", "linux", "darwin"}:
        # Detect missing counters and mistaken OS units, not a performance threshold.
        assert report["resident_peak"]["bytes"] > 1_048_576
    if scenario.endswith("rejection"):
        assert report["outcome"]["rejected_at"].startswith("expand")


def test_allocation_pass_has_no_contaminated_timing_or_resident_counter():
    result = call("--worker", "release_suite", "--mode", "allocations")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "outcome": {"passed_cases": 8},
        "python_allocation_peak_bytes": report["python_allocation_peak_bytes"],
    }
    assert report["python_allocation_peak_bytes"] > 0


def test_report_records_raw_samples_environment_and_digest(tmp_path):
    path = tmp_path / "measurement.json"
    result = call("--samples", "2", "--scenario", "release_suite", "--output", str(path))
    assert result.returncode == 0, result.stderr
    assert not result.stdout
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["sample_count"] == 2
    assert len(report["startup_ns"]["samples"]) == 2
    assert (
        report["startup_ns"]["min"] <= report["startup_ns"]["median"] <= report["startup_ns"]["max"]
    )
    assert report["source_sha256"] == benchmark.content_hash()
    assert report["environment"]["python"]
    measurement = report["measurements"][0]
    assert len(measurement["samples"]) == 2
    assert measurement["units_per_second"] > 0
    assert all(sample["outcome"] == {"passed_cases": 8} for sample in measurement["samples"])
    original = path.read_bytes()
    refused = call("--output", str(path))
    assert refused.returncode == 1
    assert "already exists" in refused.stderr
    assert path.read_bytes() == original


@pytest.mark.parametrize("value", ["0", "21", "-1", "invalid"])
def test_sample_count_is_bounded(value):
    result = call("--samples", value)
    assert result.returncode == 2
    assert not result.stdout


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError, match="unknown benchmark"):
        benchmark.workload("unknown")
    with pytest.raises(ValueError, match="invalid benchmark selection"):
        benchmark.collect(0, ("release_suite",))


def test_unsupported_resident_platform_is_explicit(monkeypatch):
    monkeypatch.setattr(benchmark.sys, "platform", "unsupported")
    assert benchmark.resident_peak() == {"bytes": None, "method": "unsupported_platform"}


def test_unexpected_suite_failure_is_not_measured_as_success(monkeypatch):
    import samsarix_spirals

    class Failed:
        successful = False

    monkeypatch.setattr(samsarix_spirals, "run_suite", lambda *_: Failed())
    execute, _, _ = benchmark.workload("release_suite")
    with pytest.raises(RuntimeError, match="outcome changed"):
        execute()


def test_timeouts_and_child_failures_fail_report(monkeypatch, capsys):
    def fail(*_):
        raise subprocess.TimeoutExpired("fixed benchmark worker", 60)

    monkeypatch.setattr(benchmark, "invoke", fail)
    assert benchmark.main(["--samples", "1", "--scenario", "release_suite"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "timed out" in captured.err


def test_source_changes_invalidate_measurement(monkeypatch):
    hashes = iter(["before", "after"])
    responses = iter(
        [
            "samsarix-spirals 0.1.0",
            "samsarix-spirals 0.1.0",
            json.dumps({"elapsed_ns": 100, "units": 8, "outcome": {"passed_cases": 8}}),
            json.dumps({"python_allocation_peak_bytes": 1000, "outcome": {"passed_cases": 8}}),
        ]
    )
    monkeypatch.setattr(benchmark, "content_hash", lambda: next(hashes))
    monkeypatch.setattr(benchmark, "invoke", lambda _: next(responses))
    with pytest.raises(RuntimeError, match="changed during measurement"):
        benchmark.collect(1, ("release_suite",))
