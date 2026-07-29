# Samsarix Spirals roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **experiment or learning project**. Keep this as an evidence-producing experiment or reference. Promotion to a supported product requires a real consumer and a measured advantage over the simpler alternative.
Planned repository identity: `Deathcharge/samsarix-spirals` (ready-reference).

Current disposition: Merge as a labeled reference or experiment; do not imply production support.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Review priority: Prove one real schema-v1 consumer.
- Review priority: otherwise tag a reviewed reference snapshot and freeze feature investment.

## Release candidate

- Define a falsifiable evaluation against a simpler baseline.
- Publish fixtures, limits, and reproducible results without overstating conclusions.
- Tag and freeze a useful reference if the experiment does not earn adoption.

Current hardening backlog:

- Only `set` and `assert`; many users can express the same job directly in tests or a short script.
- A new workflow schema creates another compatibility contract in an already crowded orchestration portfolio.
- No consumer, published JSON Schema, external adoption, release, or migration path from the removed prototype.
- The deletion-heavy PR needs careful legal/history review despite the superior direction.
- Repository slug remains Helix-named while distribution/import/CLI use Samsarix.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
