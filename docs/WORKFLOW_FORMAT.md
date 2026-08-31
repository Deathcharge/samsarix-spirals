# Workflow format

This document defines workflow schema version `1` for Samsarix Spirals `0.1.x`.

## Document shape

```json
{
  "schema_version": 1,
  "name": "hello",
  "description": "Optional human-readable text.",
  "defaults": {
    "punctuation": "!"
  },
  "steps": [
    {
      "id": "greeting",
      "uses": "set",
      "with": {
        "message": "Hello, {{ input.name }}{{ defaults.punctuation }}"
      }
    }
  ],
  "output": "{{ steps.greeting }}"
}
```

Top-level fields:

| Field | Required | Contract |
| --- | --- | --- |
| `schema_version` | yes | Integer `1`. |
| `name` | yes | Non-empty string, at most 100 characters. |
| `description` | no | String or `null`, at most 500 characters. |
| `defaults` | no | JSON object available to templates. Defaults to `{}`. |
| `steps` | yes | Non-empty array of at most 1,000 ordered steps. |
| `output` | no | Rendered after all steps. Without it, the last step output is returned. |

Unknown fields are rejected. JSON object keys must be unique. Documents must be UTF-8,
at most 1 MiB, at most 20 levels deep, and contain only finite JSON numbers.

## Steps

Each step has exactly three fields:

- `id`: starts with a letter, then contains up to 63 letters, digits, `_`, or `-`.
- `uses`: one of `set`, `assert`, `merge`, `pick`, `map`, `filter`, or `normalize`.
- `with`: an object containing operation arguments.

IDs are unique and case-sensitive. A step can reference only earlier steps. Execution is
sequential and fail-fast.

### `set`

`set` recursively renders its `with` object and exposes that object as the step output.
It has no external side effect.

```json
{
  "id": "summary",
  "uses": "set",
  "with": {
    "title": "Order {{ input.order_id }}",
    "items": "{{ input.items }}"
  }
}
```

The exact placeholder around `input.items` preserves an array or object. Embedding an
array or object inside surrounding text is rejected during execution.

### `assert`

`assert` requires `value` and `operator`. `message` is an optional failure message.
Operators that compare against another value also require `expected`.

| Operator | `expected` | Behavior |
| --- | --- | --- |
| `equals`, `not_equals` | yes | JSON equality or inequality. |
| `truthy`, `falsy`, `not_empty` | no | Boolean or empty-value checks. |
| `contains` | yes | Membership in a string, array, or object keys. |
| `greater_than`, `greater_or_equal` | yes | Ordered comparison. |
| `less_than`, `less_or_equal` | yes | Ordered comparison. |

Ordered operands must both be numbers or both strings. Booleans are not treated as
numbers. A successful assertion exposes `{"passed": true, "value": ...}`. A failed
assertion stops the workflow and makes the CLI exit `1`.

`equals`, `not_equals`, array `contains`, and suite output expectations all use the same
recursive JSON equality: `true` differs from `1`, `false` differs from `0`, and `1` equals
`1.0`. Arrays compare in order and objects compare by keys and values independent of key
order. This type distinction applies inside nested arrays and objects too.

`truthy` and `falsy` intentionally test coercible truth values, not boolean types: the
non-empty string `"false"` is truthy. For an approval or enabled-state gate, use `equals`
with the literal `true` or `false`. Prefer an explicit allowed value for policy states
(for example, `equals: "private"`) rather than excluding only a single bad value.

### `merge`

`merge` requires `objects`, which must render to an array of objects. It creates a new
object by applying those objects from left to right. When a key occurs more than once,
the value in the later object wins.

```json
{
  "id": "enriched",
  "uses": "merge",
  "with": {
    "objects": [
      "{{ input.result }}",
      {"source": "agent", "reviewed": true}
    ]
  }
}
```

The operation is shallow: nested objects are replaced, not recursively merged. Inputs
are copied, so later processing cannot mutate workflow defaults or prior step outputs.
The normal collection and total-value budgets apply to the result.
Place trusted policy values last when untrusted input must not override them.

### `pick`

`pick` requires `object` and `keys`. It returns a new object containing only the named
top-level keys, in the order given by `keys`.

```json
{
  "id": "public_result",
  "uses": "pick",
  "with": {
    "object": "{{ steps.enriched }}",
    "keys": ["ticket_id", "summary", "source"]
  }
}
```

`keys` must render to an array of unique strings. By default, every named key is required
and a missing key fails the step. Set `required` to `false` to omit missing keys instead.
`pick` is an allowlist rather than a redaction list: every field that may leave the
workflow boundary must be named explicitly.
Selection is top-level only: naming an object-valued key retains that entire nested
object. It does not recursively remove sensitive child fields.

### `map`

`map` requires `items` (an array or exact template) and `template` (any JSON value).
It renders the template once per item and returns an array in the original order:

```json
{
  "id": "names",
  "uses": "map",
  "with": {
    "items": "{{ input.targets }}",
    "template": {"name": "{{ item.name }}", "source": "{{ defaults.source }}"}
  }
}
```

`item` is the current JSON value, so `{{ item }}` also supports scalar items. The
`input`, `defaults`, and prior `steps` roots remain available. `item` is valid only in
`map.template` or `filter.where`, never in the source `items`, another operation, or
final output. There is no index variable, nested operation, executable expression, or
second rendering of template-looking text obtained from input. Keys are literal,
as in `set`. Each input item produces exactly one output, including `null`.

### `filter`

`filter` requires `items` and a `where` object containing `value`, a literal `operator`,
and `expected` when the operator requires it. It uses the same comparisons as `assert`,
but a false comparison excludes the item instead of failing the step. Custom `message`
is not supported. For example:

```json
{
  "id": "enabled",
  "uses": "filter",
  "with": {
    "items": "{{ input.targets }}",
    "where": {"value": "{{ item.enabled }}", "operator": "equals", "expected": true}
  }
}
```

Missing fields or invalid operand types are execution errors, not silent exclusions.
An item with `enabled: 1` does not equal boolean `true`. Matching items are copied whole;
use a subsequent `map` to select/rename fields if needed. Neither operation deduplicates
or sorts. Both return `[]` for empty input without evaluating their bodies, but malformed
body syntax, unknown operators, and invalid static references are rejected even then.

List operations render the source array once. A map's entire output shares one
50,000-value/4 MiB budget, including its array root. Filter predicate renders share one
50,000-value/4 MiB work budget across **all** items, including excluded items; its output
has a separate shared budget. No limit resets per item. The 10,000-item and composed
depth limits still apply. Each list operation counts as one workflow step, while its
iteration is bounded by these array/work budgets. Per-item failures identify the step
and zero-based `item[N]`; no partial success result is returned.

### `normalize`

`normalize` requires `value` and `transforms`. The value must render to a string or an
array of strings; it returns the same scalar/array shape. `transforms` is a static list
of one to three names, applied in the listed order:

- `trim`: removes only ASCII space, tab, CR, LF, vertical tab, and form feed at both ends.
- `ascii_lower`: changes `A`–`Z` to `a`–`z`.
- `ascii_upper`: changes `a`–`z` to `A`–`Z`.

```json
{
  "id": "normalized",
  "uses": "normalize",
  "with": {"value": "{{ steps.names }}", "transforms": ["trim", "ascii_lower"]}
}
```

Non-ASCII characters are unchanged, making these transforms independent of locale and
Unicode database changes. There is no implicit string conversion, Unicode casefolding,
regex replacement, validation, escaping, or sanitization. Empty strings/arrays remain
valid. A non-string array element fails with its index. Input and output remain bounded
by the existing limits; these transforms cannot increase string size.

### Final output versus trace

`run` normally serializes the final output together with every completed step output.
Later selection cannot remove values from earlier trace entries. Use `run --output-only`
to serialize only the raw final JSON value, or `RunResult.output` from Python. The default
trace and `RunResult.to_dict()` remain useful for local diagnostics but are not redacted.
Both output modes fail without partial stdout. Neither mode sanitizes values deliberately
included in the final result, or input interpolated into custom assertion error messages.

## Templates

Templates use `{{ reference.path }}`. Available roots are:

- `input`: the JSON object supplied to the run;
- `defaults`: the workflow's `defaults` object;
- `steps`: outputs from completed steps, addressed by step ID.

Object keys use dot segments. Numeric segments index arrays, for example
`{{ input.items.0.name }}`. Keys containing dots cannot be addressed in schema version 1.

An exact placeholder preserves the referenced JSON type:

```json
{"items": "{{ input.items }}"}
```

Embedded placeholders render scalar values as text:

```json
{"message": "Hello, {{ input.name }}!"}
```

Missing paths, malformed braces, forward step references, and unknown roots are errors.
Schema version 1 has no escaping syntax for literal `{{` or `}}`.

## Limits and determinism

The CLI executes at most 100 steps by default. `--max-steps` can raise this cap up to
the schema limit of 1,000. A validated or rendered string contains at most 100,000
characters, and each validated or rendered JSON tree contains at most 50,000 values.
The runner performs no I/O after loading input, does not read
environment variables, and does not add time, randomness, or identifiers to results.
Given the same workflow, input, and run limit, its JSON value result is the same.

The 20-level nesting limit applies to the composed rendered tree, not just its input
pieces. A placeholder nested ten levels into the result has only ten further levels
available to its referenced value. This also applies when wrapping prior-step output
and when rendering the final output; an over-depth composition fails before being emitted.

Object key order is not semantic. The CLI sorts keys when serializing its result.

### Encoded payload budgets

Each step's rendered arguments and the explicit final rendered value are limited to
**4 MiB (4,194,304 bytes)**. All retained step outputs plus the final output together
are limited to **16 MiB (16,777,216 bytes)**. The implicit final copy of the last step
counts again; earlier outputs still count when `--output-only` hides the trace. Limits
are inclusive and reset on each run, including each regression-suite case.

Accounting uses compact JSON with ASCII escaping (`ensure_ascii=True` and separators
`(',', ':')`): object keys, quotes, punctuation, escaped controls, and Unicode escape
sequences all count. This is a deterministic payload measure, not the CLI's formatting
choice. Rendering is charged incrementally; cumulative accounting iterates encoded
fragments instead of constructing another full serialized document. Even arguments
discarded by `pick` or overwritten by `merge` must fit the per-render budget.

Exceeding a budget raises an execution error (CLI exit `1`) without partial stdout.
Step failures carry the step ID; final-output failures have no step ID. Reduce repeated
data, select smaller inputs upstream, or split a batch into independent runs. There is
no flag to disable these limits.

These are not exact stdout-byte or process-memory limits: pretty-print whitespace,
trace metadata, interpreter overhead, temporary copies, and caller-owned API objects
are not included. They are also not CPU deadlines or an isolation sandbox. Apply OS
resource limits when embedding the runner in a service; hostile multi-tenant hosting
is not a supported deployment. API factories normalize validated mappings/tuples into
detached JSON objects/arrays. Use those factories and do not mutate validated workflow
internals; subsequently caller-mutated results are outside the execution guarantee.

## Static explanations

`samsarix-spirals explain WORKFLOW` validates a workflow and emits an `explain_version`
`1` JSON document without rendering templates or executing steps. It includes:

- the lexicographically sorted `input_paths` and `default_paths` referenced anywhere;
- each step's operation, direct prior-step dependencies, and direct input/default paths;
- `item_paths` on map/filter steps, listing their local item references separately;
- the final output's direct dependencies and paths.

Paths preserve their template spelling, such as `input.items.0.name`. A reference to a
whole root is reported as `input` or `defaults`. Dependencies are step IDs, not workflow
values. When a workflow omits `output`, the explanation records the last step as the
implicit output dependency.

The report intentionally excludes defaults, inputs, resolved output, and other values.
This makes it suitable for code-review and inventory tooling, but it does not prove that
runtime input will contain every reported path; regression suites remain the executable
contract.

## Regression suite format

The `test` command accepts a workflow and a separate suite document. Suite version `1`
has this shape:

```json
{
  "suite_version": 1,
  "name": "release contract",
  "cases": [
    {
      "name": "approved release",
      "input": {"approved": true},
      "expect": {"output": {"publish": true}}
    },
    {
      "name": "unapproved release",
      "input": {"approved": false},
      "expect": {
        "error": {
          "step_id": "require_approval",
          "message_contains": "approval is required"
        }
      }
    }
  ]
}
```

A suite contains between 1 and 1,000 uniquely named cases. Each case has an optional
`input` object and exactly one expectation:

- `output` compares the workflow's final JSON value using exact JSON equality;
- `error` expects execution to fail and can constrain `step_id`, `message_contains`,
  both, or neither.

Unknown fields are rejected. Suite files use the same 1 MiB, UTF-8, unique-key,
finite-number, nesting, string, collection, and total-value limits as workflow and input
documents. A suite runs all cases even after a mismatch. Human and JSON reports avoid
echoing fixture values.

### Published structural schemas

The distribution bundles JSON Schema Draft 2020-12 documents for workflow and suite
version `1`. Retrieve the exact installed versions with:

```console
samsarix-spirals schema workflow
samsarix-spirals schema suite
```

The schemas intentionally cover portable structural constraints. The runtime additionally
enforces requirements JSON Schema cannot express here, including the 1 MiB byte limit,
maximum nesting and total-value budgets, unique step IDs and case names, template syntax,
default existence, and prior-step reference ordering. Passing external schema validation
does not replace `samsarix-spirals validate` or `samsarix-spirals test`.

### JUnit reports

`samsarix-spirals test WORKFLOW SUITE --junit` emits deterministic JUnit XML on standard
output. It includes no timestamps, durations, fixture values, or workflow outputs. Invalid
XML 1.0 characters in user-provided suite, workflow, or case names are replaced with the
Unicode replacement character so the report always remains parseable.
