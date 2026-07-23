# RAIP V9 — Simulation & Validation Domain

V9 is an independent passive, read-only, deterministic, offline-only domain. It validates
executive decision packages against supplied historical snapshots before any separate learning
process may consider them. This implements Rule #021: no learning candidate is supported unless
validated historical replay has complete evidence lineage.

## Modules and outputs

`HistoricalReplayEngine` writes `historical_replay.json` and `replay_summary.json`.
`ScenarioGenerator` writes `scenario_summary.json` for trending, range, volatile, and low
liquidity conditions discovered from historical market context. `CounterfactualAnalyzer` applies
only explicit `estimated_impact.historical_*_delta` values and records confidence and assumptions.
`ValidationReportBuilder` writes explainable `validation_report.json`. `ValidationRepository`
creates immutable, append-only `validation_repository.json` records.

## Storage and safety

All output is rooted at `simulation/historical_replay/`, `simulation/validation/`, and
`simulation/validation_repository/`. Atomic write-once files and stable SHA-256 identities make
retries safe. Validation runs through a single asynchronous worker and imports no runtime,
executor, writer, broker safety, deployment, governance-mutation, recommendation-mutation, or
learning code. V9 rejects executive packages outside the supported 7.x contract rather than
attempting to interpret them.
