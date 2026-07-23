# RAIP V7 — Executive Decision Intelligence Domain

The Executive Domain is a passive, asynchronous consumer of validated recommendation repositories and the Governance health report. It produces deterministic decision candidates (one per recommendation category/business issue), detects but never resolves conflicts, ranks candidates, and creates CEO-review packages.

## Boundary and safety

It imports no Trading Domain code and never reads or writes `decision.json`, runtime payloads, execution state, confidence, thresholds, strategy, Writer, Executor, Broker Safety, or deployment controls. A missing/unhealthy Governance report marks a package blocked; every package remains approval-required. Failures are logged by the asynchronous coordinator and leave trading unaffected.

## Storage and immutability

Outputs live below `executive/decision_packages/`, `executive/decision_repository/`, and `executive/readiness/`. Writes use `*.tmp`, `fsync`, then rename. Decision package and repository files are write-once by `decision_id`; the repository is append-only and cannot replace an existing decision.

## Determinism and lineage

The decision ID derives from the business issue and sorted validated recommendation IDs. Ranking is deterministic: recommendation priority, Governance health, supporting Insight count, and historical evidence coverage. Packages preserve all recommendation, knowledge, evidence, and snapshot identifiers, and contain the V7 metadata contract including the Governance version and baseline commit.
