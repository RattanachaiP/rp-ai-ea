# PR264 — Execution Integration

PR264 connects the immutable PR263 `ExecutionPlan` to the existing V27 `Executor`
without moving broker authority. The boundary consumes only an `ExecutionPlan`, its
ready-only `ExecutorContract`, an immutable Runtime health snapshot, replay identities,
and an immutable broker snapshot. It does not inspect market, decision, or risk inputs.

## Flow and authority

`ExecutionPlan -> atomic publication -> replay validation -> ExecutorContract adapter
-> existing V27 Executor`.

The adapter performs a field-for-field projection into the established
`WriterReadResult` interface. It does not call a broker. Only the injected V27
Executor may submit an order. PR264 has no production mode and cannot promote itself.
Demo delivery requires both an isolated-demo assertion and a human approval gate.

## Publication schema

`V28.PUBLISHED_EXECUTION_PLAN.1.0` contains the exact canonical plan payload,
ExecutionPlan replay identity, Decision replay identity, Runtime sequence, and an
integrity identity over the complete envelope. Publication uses a same-directory
temporary file, file `fsync`, atomic replace, and directory `fsync`.

## Replay and fail-closed behavior

Validation binds plan integrity, ExecutorContract integrity and lineage, Decision
replay identity, execution replay identity, Runtime sequence, broker symbol/sequence,
publication integrity, Runtime health, and boundary freshness. Any mismatch blocks
delivery before the Executor is invoked.

Shadow execution records BUY, SELL, or HOLD plus expected fill, stop, target, Decision
replay identity, and ExecutionPlan replay identity. Every record fixes
`ordersend_permitted=false`; the shadow component has no broker dependency.
