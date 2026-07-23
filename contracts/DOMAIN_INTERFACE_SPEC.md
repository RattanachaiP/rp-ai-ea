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
