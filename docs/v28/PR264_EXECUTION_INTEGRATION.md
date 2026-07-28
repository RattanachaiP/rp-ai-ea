# PR264 — Execution Integration

PR264 connects the immutable PR263 `ExecutionPlan` to the existing V27 `Executor`
without moving broker authority. The boundary consumes only an `ExecutionPlan`, its
ready-only `ExecutorContract`, an immutable Runtime health snapshot, replay identities,
and an immutable broker snapshot. It does not inspect market, decision, or risk inputs.

## Flow and authority

`ExecutionPlan -> atomic publication -> replay validation -> ExecutorContract adapter
-> existing V27 Executor`.

The adapter performs a field-for-field projection from the replay-bound
`V27ExecutorCompatibilityContract` into the established `WriterReadResult` interface.
It creates no permission fields and does not call a broker. The nominal `DemoExecutor`
capability can be constructed only with a verified `DEMO` environment and internally
owns the unchanged V27 Executor. PR264 has no production mode and cannot promote itself.
Demo delivery requires an immutable environment contract and an independently replay-
validated, plan/contract/environment-specific `HumanApprovalRecord`.

## Publication schema

`V28.PUBLISHED_EXECUTION_PLAN.2.0` contains immutable canonical plan JSON, its SHA-256,
publisher authority and instance, timestamp, destination, generation, policy,
ExecutionPlan and Decision replay identities, Runtime sequence, and a replay identity
over the complete envelope. Publication uses a same-directory temporary file, file
`fsync`, atomic replace, and directory `fsync`.

## Replay and fail-closed behavior

Validation binds plan integrity, ExecutorContract integrity and lineage, Decision
replay identity, execution replay identity, Runtime sequence, broker symbol/sequence,
publication integrity, governed Runtime-health and broker observations, explicit Demo
environment authority, explicit human approval, and complete time/freshness lineage.
Every contract-to-plan execution field is compared. Any mismatch blocks delivery
before the Executor is invoked. Delivery returns an immutable replay-bound receipt,
never an opaque downstream result.

Shadow execution records BUY, SELL, or HOLD plus expected fill, stop, target, Decision
replay identity, and ExecutionPlan replay identity. Every record fixes
`ordersend_permitted=false`; the shadow component has no broker dependency.
