# Resource measurements and operating guidance

Spirals is intended for small, local JSON contracts. Encoded-value limits are not process
memory limits, and deterministic output does not imply constant execution time. Measure
your actual workloads on the intended interpreter and runner before setting capacity.

## Reproduce the measurements

From a source checkout with Python 3.11 or newer (no third-party modules required):

```console
python -I tools/benchmark.py --samples 5 --output benchmark.local.json
```

The output file must not exist. Omit `--output` to print JSON. Progress goes to stderr.
Use `--scenario release_suite` to select one workload; repeat the option for several.
`--samples` is bounded to 1–20. Each child has a 60-second timeout; any timeout, unexpected
outcome, child failure, or source change invalidates the run rather than generating a
successful partial report. Larger selections can take several minutes. The timeout bounds
each child, not total benchmark duration or memory. No daemon or network access is used.

This maintainer tool deliberately imports the checkout's `src` in isolated child Python
processes; it does not measure an arbitrary installed wheel. It also ships in the source
distribution, not the installed runtime package. Installed-package behavior is separately
checked by `tests/installed_smoke.py`.

Python `-I` ignores user-site packages and `PYTHON*` variables, but still performs the
interpreter's system-site initialization. Use a fresh virtual environment when comparing
revisions so unrelated installed `.pth` hooks do not affect startup or process overhead.
The recorded desktop observation below used the existing development interpreter, not a
clean virtual environment. A later wheel-only environment showed different base memory;
that is another reason not to treat these observations as universal runtime requirements.

Reports include raw samples, UTC start time, interpreter/platform metadata, and a SHA-256
fingerprint of the harness, Python sources, and example JSON (with CRLF normalized to LF).
The fingerprint identifies actual content, including uncommitted changes; it is not a
signature or proof of publisher identity. The source/fixture fingerprint is checked before
and after a run. Do not edit the checkout or run competing benchmarks during measurement.
No host name, account name, fixture values, or absolute filesystem paths are recorded.

## What each number means

- **`startup_ns`:** parent-observed wall time for a new isolated Python process to import
  the checkout CLI, print `--version`, and exit. Includes process creation, bootstrap,
  imports, argument handling and captured output. One discarded launch warms caches;
  these are not cold-disk, installation-time, or direct console-launch measurements.
- **`setup_ns`:** time to build/load and validate the selected workflow, payload, and suite
  inside each fresh worker, after importing the package. Generated workloads use the
  Python API; this is not uniformly file parsing time.
- **`elapsed_ns`:** wall time for one operation plus the harness's outcome checks. Every
  timing sample is a separate process and performs one operation, without an operation
  warm-up. It excludes interpreter startup, setup, memory-counter collection and report
  emission. Garbage collection remains enabled. No allocation tracing runs in these samples.
- **`units_per_second`:** case count or run count divided by median operation time. This is
  sequential, in-process throughput for this workload, not whole-job or service capacity.
- **`resident_peak`:** OS process-lifetime high-water mark in bytes, including interpreter,
  imports, setup, retained objects and the measurement harness. Windows reports peak
  working set; Linux/macOS report maximum RSS. These counters are not directly comparable
  across OS families and are not allocation totals or deltas. Unsupported platforms report
  `null`, never a fabricated zero. Supported-platform counter failures fail the measurement.
- **`python_allocation_peak_bytes`:** one separate allocation-instrumented process per
  scenario. Tracing starts after package import and covers setup and execution. This
  excludes earlier allocations, native allocations not tracked by Python and tracer storage;
  it is neither process memory nor a leak detector. Instrumented timing is deliberately omitted.

Nanoseconds are measurement units, not a claim of nanosecond accuracy. Samples report
minimum, median and maximum; a handful of samples does not justify a p95 or confidence
interval. Record machine load and compare multiple runs on the same machine/interpreter.
Hosted CI runs one sample on each OS to verify the harness and outcomes, **not** to enforce
a noisy speed threshold or establish a performance SLA.

## Fixed scenarios

| Scenario | Work and required outcome |
| --- | --- |
| `release_suite` | Checked-in release-target suite: eight positive/negative filter/map/normalize cases pass. |
| `suite_1000` | The same eight cases cycled to 1,000 distinct names, built through the API; all pass. This reaches the suite case-count limit, not every document limit. |
| `map_10000` | Project `value` from 10,000 one-key objects; output must equal integers 0–9,999. Reaches the collection-item limit. |
| `trace_100_steps` | Retain 100 step outputs, each copying a 1,000-object list; final output and step count must match. Reaches the default step-count limit. |
| `trace_100_steps_json` | Same trace, then `to_dict()` and compact JSON serialization, matching the CLI's conversion settings; excludes terminal/pipe writing. |
| `render_rejection` | Expand a 100,000-character string 50 times; must reject the first step at the rendered-byte budget. |
| `retained_rejection` | Six steps each expand that string 30 times; must reject step six at the combined-output budget. |

These are representative stress probes, **not an exhaustive maximum-memory proof**.
They do not combine all supported maxima (including the opt-in 1,000-step ceiling), all
Unicode shapes, concurrent executions, long-lived-process retention or caller-held results.
Synthetic repeated suites are not independent consumer adoption or 1,000 real user runs.

## Operating guidance

### Recorded Windows observation (2026-08-31)

[Raw five-sample report](benchmarks/windows-cpython314.json), produced by
`python -I tools/benchmark.py --samples 5 --output docs/benchmarks/windows-cpython314.json`.
The measured harness/runtime/fixtures are committed in `4cda66f`; fingerprint:
`37e34b5542cbddeb219623c892bb27bdd1282bae46297a89bc1bc3c1e395316d`.

Environment: CPython 3.14.7, Windows 11 AMD64, Intel Core i5-10310U (four cores/eight
logical CPUs). This was an ordinary desktop session, not a reserved or frequency-locked
machine. The project's test run had finished, but unrelated system load was not controlled.
Startup median was **449 ms**, range **376–494 ms**.

| Scenario | Operation median (min–max), ms | Largest observed process peak, MiB | Separate Python allocation peak, MiB |
| --- | ---: | ---: | ---: |
| Eight-case release suite | 1.91 (1.55–4.04) | 44.68 | 1.14 |
| 1,000-case suite | 185.91 (175.43–292.27) | 45.37 | 1.13 |
| 10,000-item map | 278.77 (147.40–421.17) | 50.81 | 6.28 |
| 100-step trace | 2,201.20 (1,392.16–2,636.63) | 83.12 | 37.70 |
| 100-step trace plus compact JSON | 1,688.82 (1,584.45–3,370.58) | 86.08 | 39.36 |
| Render-byte rejection | 35.05 (30.12–42.45) | 44.47 | 0.21 |
| Retained-byte rejection | 241.73 (213.90–289.13) | 44.70 | 0.42 |

The 1,000-case operation corresponds to about 5,379 cases/second, excluding setup and
startup. Timing variation is substantial: the serialization workload's lower median is
**not evidence that serialization accelerates execution**. These are independent samples,
not paired comparisons or optimized/unoptimized measurements. The allocation peaks and
resident peaks come from different processes and must not be added together.

The useful capacity observation is that a valid retained trace exceeded 80 MiB of process
memory even while remaining within encoded-output limits. This does not establish a
sufficient deployment memory allowance, universal ceiling or vulnerability. Investigate
trace-copy costs and combined-limit workloads before making stronger capacity claims.

### Trace ownership comparison (2026-08-31)

The runner now shares one private step-output tree between its lookup index and result
record, and transfers already-detached argument nodes into `set`, `assert`, `merge`, and
`pick` outputs. Every later context reference still clones through the bounded renderer;
final output and public report conversion remain detached. No limits were relaxed.

Both [before](benchmarks/trace-before.json) and [after](benchmarks/trace-after.json) reports
used the same fresh, otherwise empty virtual environment on the Windows/CPython 3.14.7
desktop described above. The before source is `3446edb`, the after source is `96e3324`.
Their respective harness/runtime/fixture fingerprints are
`1d434e8f671ac6eea02e59c42d8e54953222f7ed50bd5318babe47aa1dbbbf6c` and
`82b2e9d41c62d30c87478aa37df837e1fa6486ba28262fbd237a4804f76c5d07`.
Run this command at each revision, choosing a distinct, nonexistent report filename:

```console
python -I tools/benchmark.py --samples 5 --scenario trace_100_steps --scenario trace_100_steps_json --scenario suite_1000 --output comparison.local.json
```

| Scenario | Python allocation peak before → after, MiB | Largest observed process peak before → after, MiB | Operation median before → after, ms |
| --- | ---: | ---: | ---: |
| 100-step trace | 37.70 → 19.11 | 64.90 → 45.46 | 4,197.60 → 868.25 |
| Trace plus compact JSON | 39.36 → 39.36 | 67.99 → 67.61 | 6,241.73 → 1,498.70 |
| 1,000-case suite | 1.13 → 1.13 | 27.26 → 27.15 | 252.69 → 202.67 |

The trace-only allocation peak nearly halved. Report conversion still copies public
trees, so the serialized-report high-water mark was essentially unchanged. This is a
specific workload observation, not a universal memory ceiling or reduction guarantee.

Timing is confounded: before and after were sequential desktop runs, not randomized
paired trials; unrelated system load was uncontrolled. Even startup (unaffected by the
copy change) moved from a 1,057 ms median to 388 ms. Do not interpret the operation-time
ratios as an established speedup. Raw files retain all samples, including wide ranges.
The earlier development-interpreter observation remains historical evidence and is not
the baseline for this fresh-environment comparison.

### Apply measurements to a deployment

- Use one suite invocation for a batch rather than starting a Python process per case.
- Prefer `--output-only` when downstream tooling needs only the final value. This avoids
  full-trace report conversion/serialization, but the runner still retains step results
  during execution; it is not streaming execution or a lower memory-limit guarantee.
- Bound concurrent jobs separately. Each worker has interpreter overhead and may retain
  multiple detached Python object trees. Do not size RAM from the 16 MiB encoded limit.
- Configure CI/job deadlines and OS/container memory limits when processing untrusted
  documents. The pure runner is not an OS sandbox and has no wall-clock cancellation API.
- Use measured whole-job duration, not only `units_per_second`, for cost estimates:
  `job count × billed duration × your runner rate`. Include provisioning, file validation,
  report emission and retries. Spirals itself has no service/API usage fees or telemetry.

Measurement references: Python's [isolated-mode boundary](https://docs.python.org/3/using/cmdline.html#cmdoption-I),
[performance clock](https://docs.python.org/3/library/time.html#time.perf_counter_ns),
[allocation tracing](https://docs.python.org/3/library/tracemalloc.html),
[Unix resource counters](https://docs.python.org/3/library/resource.html),
[Linux maximum RSS units](https://man7.org/linux/man-pages/man2/getrusage.2.html),
[Darwin maximum RSS units](https://github.com/apple/darwin-xnu/blob/main/bsd/man/man2/getrusage.2),
and Microsoft's [process memory counters](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).
