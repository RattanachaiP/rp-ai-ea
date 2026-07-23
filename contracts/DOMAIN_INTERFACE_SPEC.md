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

**Input:** immutable governance report, finalized executive package, completed successful
simulation validation report, and declared evidence-to-simulation lineage. Inputs are read
only and rejected safely when their major schema versions are not V6, V7, and V9 respectively.

**Outputs:** `qualification_report.json`, `lineage_verification.json`, immutable individual
candidate records plus an append-only `learning_candidate_queue.json` index, and
`learning_readiness.json`, below `learning_intake/`.

**Hard boundary:** V10 qualifies historical artefacts only. It cannot train a model, update
weights, optimize strategy, modify runtime/recommendations/governance/executive decisions,
deploy software, or influence live trading.

**Execution:** callers use `LearningIntakeCoordinator.intake_async()` for isolated single-worker
post-validation work. All writes use atomic replacement or atomic write-once records.
