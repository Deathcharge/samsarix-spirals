# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Samsarix LLC
"""Fixed-workload, fresh-process measurements; not part of the installed runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess  # nosec B404
import sys
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    "release_suite",
    "suite_1000",
    "map_10000",
    "trace_100_steps",
    "trace_100_steps_json",
    "render_rejection",
    "retained_rejection",
)
CHILD_TIMEOUT = 60
BOOTSTRAP = (
    "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
    "runpy.run_module('samsarix_spirals',run_name='__main__')"
)


def workload(name):
    """Return a validated workload and an operation that checks its actual outcome."""
    from samsarix_spirals import (
        Workflow,
        WorkflowExecutionError,
        WorkflowSuite,
        load_suite,
        load_workflow,
        run_suite,
        run_workflow,
    )

    if name in {"release_suite", "suite_1000"}:
        workflow = load_workflow(ROOT / "examples/release-targets.json")
        if name == "release_suite":
            suite = load_suite(ROOT / "examples/release-targets.suite.json")
        else:
            document = json.loads(
                (ROOT / "examples/release-targets.suite.json").read_text(encoding="utf-8")
            )
            cases = document["cases"]
            document["cases"] = [
                {**cases[index % len(cases)], "name": f"case-{index}"} for index in range(1000)
            ]
            suite = WorkflowSuite.from_dict(document)

        def execute():
            result = run_suite(workflow, suite)
            if not result.successful or result.passed != len(suite.cases):
                raise RuntimeError("benchmark suite outcome changed")
            return {"passed_cases": result.passed}

        return execute, len(suite.cases), "cases"

    if name == "map_10000":
        payload = {"items": [{"value": index} for index in range(10_000)]}
        steps = [
            {
                "id": "map",
                "uses": "map",
                "with": {
                    "items": "{{ input.items }}",
                    "template": "{{ item.value }}",
                },
            },
        ]
        expected = list(range(10_000))
        step_count = 1
    elif name in {"trace_100_steps", "trace_100_steps_json"}:
        payload = {"items": [{"value": index} for index in range(1000)]}
        steps = [
            {"id": f"copy{index}", "uses": "set", "with": {"items": "{{ input.items }}"}}
            for index in range(100)
        ]
        expected = payload
        step_count = 100
    elif name in {"render_rejection", "retained_rejection"}:
        payload = {"text": "x" * 100_000}
        count, step_count = (50, 1) if name == "render_rejection" else (30, 6)
        steps = [
            {
                "id": f"expand{index}",
                "uses": "set",
                "with": {
                    "items": ["{{ input.text }}"] * count,
                },
            }
            for index in range(step_count)
        ]
        expected = None
    else:
        raise ValueError(f"unknown benchmark scenario: {name}")
    workflow = Workflow.from_dict({"schema_version": 1, "name": name, "steps": steps})

    def execute():
        try:
            result = run_workflow(workflow, payload)
        except WorkflowExecutionError as error:
            expected_step = {"render_rejection": "expand0", "retained_rejection": "expand5"}
            expected_text = {
                "render_rejection": "rendered value exceeds the ",
                "retained_rejection": "combined output exceeds the ",
            }
            if (
                name not in expected_step
                or error.step_id != expected_step[name]
                or expected_text[name] not in str(error)
                or "-byte limit" not in str(error)
            ):
                raise RuntimeError("benchmark rejection contract changed") from error
            return {"rejected_at": error.step_id}
        if (
            name.endswith("rejection")
            or result.output != expected
            or len(result.steps) != step_count
        ):
            raise RuntimeError("benchmark workflow outcome changed")
        if name == "trace_100_steps_json":
            serialized = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)
            return {
                "completed_steps": len(result.steps),
                "serialized_bytes": len(serialized.encode("utf-8")),
            }
        return {"completed_steps": len(result.steps)}

    return execute, 1, "runs"


def resident_peak():
    """OS high-water mark, including interpreter/setup; never a delta or heap limit."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetCurrentProcess.argtypes = []
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"bytes": counters.PeakWorkingSetSize, "method": "windows_peak_working_set"}
    if sys.platform in {"linux", "darwin"}:
        import resource

        scale = 1024 if sys.platform == "linux" else 1
        return {
            "bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale,
            "method": "getrusage_maxrss",
        }
    return {"bytes": None, "method": "unsupported_platform"}


def worker(name, mode):
    # Deliberate checkout source: no installed copy, PYTHONPATH or consumer imports.
    sys.path.insert(0, str(ROOT / "src"))
    import samsarix_spirals  # noqa: F401 - import cost excluded from operation timings

    if mode == "allocations":
        tracemalloc.start()
    setup_start = time.perf_counter_ns()
    execute, units, unit = workload(name)
    setup_ns = time.perf_counter_ns() - setup_start
    start = time.perf_counter_ns()
    outcome = execute()
    elapsed_ns = time.perf_counter_ns() - start
    if mode == "allocations":
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {"python_allocation_peak_bytes": peak, "outcome": outcome}
    return {
        "setup_ns": setup_ns,
        "elapsed_ns": elapsed_ns,
        "units": units,
        "unit": unit,
        "resident_peak": resident_peak(),
        "outcome": outcome,
    }


def invoke(arguments):
    # Maintainer-selected interpreter and fixed commands, never a shell or workflow code.
    completed = subprocess.run(  # noqa: S603  # nosec B603
        [sys.executable, "-I", *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=CHILD_TIMEOUT,
    )
    if completed.stderr:
        raise RuntimeError("benchmark child wrote unexpected stderr")
    return completed.stdout


def summary(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def content_hash():
    """Identify actual source/fixtures/harness, including uncommitted edits, not just HEAD."""
    digest = hashlib.sha256()
    paths = [
        Path(__file__),
        *sorted((ROOT / "src").rglob("*.py")),
        *sorted((ROOT / "examples").glob("*.json")),
    ]
    for path in paths:
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def collect(samples, scenarios):
    if not 1 <= samples <= 20 or not scenarios or any(name not in SCENARIOS for name in scenarios):
        raise ValueError("invalid benchmark selection")
    started_at = datetime.now(UTC).isoformat()
    source_hash = content_hash()
    # Exactly one warm-up, then independent interpreter launches; not cold filesystem caches.
    command = ["-c", BOOTSTRAP, str(ROOT / "src"), "--version"]
    version = invoke(command).strip()
    startup = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        if invoke(command).strip() != version:
            raise RuntimeError("CLI version changed during benchmark")
        startup.append(time.perf_counter_ns() - start)
    measurements = []
    for name in scenarios:
        print(f"Measuring {name}", file=sys.stderr, flush=True)
        arguments = [str(Path(__file__).resolve()), "--worker", name]
        # No operation warm-up: each sample executes once in a new interpreter.
        runs = [json.loads(invoke([*arguments, "--mode", "timing"])) for _ in range(samples)]
        allocation = json.loads(invoke([*arguments, "--mode", "allocations"]))
        if any(run["outcome"] != allocation["outcome"] for run in runs):
            raise RuntimeError("benchmark outcomes differ across processes")
        elapsed = [run["elapsed_ns"] for run in runs]
        measurements.append(
            {
                "scenario": name,
                "samples": runs,
                "elapsed_ns": summary(elapsed),
                "units_per_second": runs[0]["units"] * 1_000_000_000 / statistics.median(elapsed),
                "allocation_sample": allocation,
            }
        )
    if content_hash() != source_hash:
        raise RuntimeError(
            "source or fixtures changed during measurement; rerun on a stable checkout"
        )
    return {
        "benchmark_version": 1,
        "started_at": started_at,
        "source_sha256": source_hash,
        "product": version,
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "sample_count": samples,
        "child_timeout_seconds": CHILD_TIMEOUT,
        "startup_ns": {"samples": startup, **summary(startup)},
        "measurements": measurements,
    }


def sample_count(value):
    count = int(value)
    if not 1 <= count <= 20:
        raise argparse.ArgumentTypeError("samples must be between 1 and 20")
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=sample_count, default=5)
    parser.add_argument("--scenario", choices=SCENARIOS, action="append")
    parser.add_argument("--output", type=Path, help="create a new JSON report (never overwrite)")
    parser.add_argument("--worker", choices=SCENARIOS, help=argparse.SUPPRESS)
    parser.add_argument(
        "--mode", choices=("timing", "allocations"), default="timing", help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    try:
        if args.worker:
            report = worker(args.worker, args.mode)
        else:
            if args.output and args.output.exists():
                raise FileExistsError("report already exists; select a new output path")
            report = collect(args.samples, tuple(dict.fromkeys(args.scenario or SCENARIOS)))
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as target:
                target.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
