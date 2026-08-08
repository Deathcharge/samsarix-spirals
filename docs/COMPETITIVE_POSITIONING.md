# Competitive position and use cases

Research reviewed on 2026-08-08 supports a narrow product boundary for Samsarix Spirals.
The project should complement mature orchestrators and configuration languages, not
imitate their broadest capabilities.

## What adjacent products already do well

| Product | Established strength | Why Samsarix should not clone it |
| --- | --- | --- |
| [Temporal](https://docs.temporal.io/) | Durable application execution that resumes after infrastructure failures. | Competing requires a service, persistence model, worker lifecycle, and operational control plane. |
| [Prefect](https://docs.prefect.io/v3/concepts/tasks) | Observable Python tasks with retries, caching, concurrency, timeouts, and state. | Adding these features would erase the hermetic runner's small trust and deployment surface. |
| [Dagster](https://docs.dagster.io/) | Asset-oriented data orchestration with lineage, observability, and testability. | Samsarix has neither an asset catalog nor a data-platform control plane. |
| [Dagger](https://docs.dagger.io/) | Local-first, repeatable CI pipelines using containers, typed SDKs, caching, and traces. | Samsarix should stay useful where Docker and executable pipeline code are unnecessary or undesirable. |
| [CUE](https://cuelang.org/docs/concept/how-cue-enables-configuration/) | Expressive configuration constraints, validation, unification, and generation. | Recreating a constraint language would introduce far more semantic complexity than a reviewable step model needs. |
| [GitHub Actions](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows) | Event-triggered jobs and reusable actions on managed or self-hosted runners. | Samsarix can be one portable contract-checking step inside CI rather than another CI service. |

## Differentiated promise

Samsarix should optimize for a sentence a reviewer can verify:

> This checked-in JSON turns these bounded inputs into this exact output—or this expected
> step failure—without executing code or contacting another system.

That promise makes the product useful in security-sensitive and agentic development
loops where an orchestration platform is excessive but a shell or Python script creates
an unnecessarily broad execution surface.

## Initial user journeys

### Release-policy owner

The owner checks in a workflow and positive/negative cases. Developers run the suite
locally; CI runs the same command before a separate, credentialed publish job. Samsarix
never receives publishing credentials and emits only normalized JSON.

### AI application developer

The developer treats structured model output as untrusted input. A workflow asserts
required policy decisions and shapes the accepted fields. Regression cases lock in known
good and known bad responses before the output reaches a side-effecting tool.

### Platform repository maintainer

The maintainer defines small configuration or metadata policies once, stores adversarial
fixtures beside them, and receives deterministic step-scoped failures across laptops and
CI providers.

## Product guardrails

- Do not add arbitrary Python, shell, JavaScript, dynamic imports, or expression `eval`.
- Keep network, filesystem writes, environment access, time, randomness, and credentials
  outside the workflow runtime.
- Add new operations only when they are deterministic, bounded, composable, and supported
  by a flagship fixture suite.
- Prefer machine-readable artifacts and CI integration over a hosted dashboard until
  adoption proves that a control plane is necessary.
- Compare every new feature with a short script and remove it when the script is clearer.
