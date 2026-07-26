# GOVERNANCE ARCHITECTURE SPEC

## Advisory governance pipeline

The governed advisory lineage is:

`Pattern Memory -> Runtime Confidence -> Decision Context -> Decision Intelligence -> Decision Recommendation -> Execution Readiness -> Execution Environment Intelligence -> future Execution Feasibility`.

Each stage consumes only the immutable canonical record, report, or snapshot types owned by its immediate predecessor. Each stage must verify source provenance, repository and snapshot membership, policy and engine partitions, replay identity, and historical lineage. Validation fails closed.

## PR186 — Governed Advisory Execution Readiness Engine

PR186 owns only execution-readiness evaluation, identity, provenance, policy, repository, snapshot, and report artifacts. It accepts PR185 Recommendation records, reports, and snapshots and emits immutable advisory-only `ExecutionReadinessRecord`, `ExecutionReadinessReport`, and chained snapshots.

The only readiness states are `REJECTED`, `INSUFFICIENT_EXECUTION_READINESS`, and `EXECUTION_READY_FOR_ENVIRONMENT_CHECK`. The ready state means solely that the advisory governance package is internally complete and consistent enough to be inspected by future PR187. It never means BUY, SELL, trade approval, execution approval, runtime activation, or permission to call `OrderSend`.

PR186 has no authority over market analysis, strategy, bias, direction, risk construction, decision publication, execution environment measurements, spread, latency, slippage, broker communication, runtime activation, position management, exits, or execution. Execution authority remains exclusively inside the MT5 Executor.

## Repository contract

PR186 artifacts reside below `learning_data/execution_readiness/`. Records and snapshots use canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests, atomic append-only writes, collision rejection, exact replay, and a digest-linked snapshot chain. Any provenance, snapshot, repository, policy, engine-version, or replay mismatch fails closed.

## PR187 — Governed Advisory Execution Environment Intelligence Engine

PR187 owns only environment-quality evaluation, identity, provenance, policy,
repository, snapshots, and reports. It accepts PR186 `ExecutionReadinessRecord`,
`ExecutionReadinessReport`, and `ExecutionReadinessSnapshot` artifacts and emits
immutable advisory-only environment evidence. Its states are `REJECTED`,
`INSUFFICIENT_ENVIRONMENT_INFORMATION`, and `ENVIRONMENT_READY_FOR_FEASIBILITY`.
The ready state permits only future PR188 feasibility assessment and grants no
trading or execution authority.

<<<<<<< HEAD
PR187 evaluates only canonical immutable observations bound to the exact PR186
artifact and policy partition. It never infers feed, stream, session, spread,
latency, slippage, liquidity, consistency, freshness, or completeness from a
readiness state. Missing and partial evidence fail closed as
`INSUFFICIENT_ENVIRONMENT_INFORMATION`; the configured policy thresholds and
minimum quality are retained in each result's declared policy artifact.

=======
>>>>>>> origin/codex-dev
PR187 artifacts reside below `learning_data/execution_environment/` and use
canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests, atomic
append-only writes, collision rejection, exact replay, and a digest-linked snapshot
chain. All provenance, snapshot, repository, policy, engine-version, and replay
mismatches fail closed.
