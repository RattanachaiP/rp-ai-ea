# RAIP Domain Interface Specification

## Simulation & Validation Domain (V9)

**Input:** executive decision package plus explicitly supplied historical snapshots. The
domain reads these inputs only; it does not discover, alter, or repair them.

**Outputs:** `historical_replay.json`, `scenario_summary.json`, `validation_report.json`,
and immutable `validation_repository.json`, below `simulation/`.

**Hard boundary:** V9 cannot import or modify the Trading Runtime, `decision.json`, execution
state, recommendations, governance, executive packages, deployment controls, or learning
datasets. Its counterfactuals are historical-only and apply only explicitly recorded historical
impact deltas. They are not live-market forecasts.

**Execution:** callers use `SimulationCoordinator.validate_async()` for asynchronous,
single-worker processing. Failure is isolated from runtime operations.

## Learning Intake Domain (V10)

**Input:** immutable governance, executive, validation, and declared lineage artefacts. The explicit, versioned `learning_intake_policy.json` controls qualification; inputs remain read-only.

**Outputs:** immutable `learning_intake_report.json`, `lineage_verification.json`, per-candidate records, append-only `learning_candidate_registry.json`, and `learning_readiness.json`, below `learning_intake/`. The registry is a catalog, never a scheduler or executable queue.

**Hard boundary:** V10 only publishes offline qualification artefacts. It cannot train, update weights, modify thresholds, runtime payloads, recommendations, governance, executive decisions, deployment, or live trading.

**Execution:** `LearningIntakeCoordinator.intake_async()` uses an isolated single worker. Publication is atomic and immutable records are write-once.
