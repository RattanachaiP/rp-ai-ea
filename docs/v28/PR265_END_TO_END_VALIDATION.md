# PR265 — V28 End-to-End Validation

## Architecture validation report

PR265 validates the four governed hand-offs from immutable Market/Decision context through
Risk, Execution, and atomic publication. Checks cover contract identity, policy and replay
lineage, runtime sequence, freshness, data consistency, ExecutionPlan, ExecutorContract, and
publication payload integrity.

## Replay validation report

The replay checker independently constructs the same artifact at least twice and requires
both value equality and one identical replay identity. Missing identity or any output drift
fails certification.

## Shadow execution report

The shadow runner requires expected BUY, SELL, and HOLD coverage, repeats every case, and
requires identical records. Every record has `mode=SHADOW` and
`ordersend_permitted=false`; the runner has no broker dependency or submission path.

## Certification and runtime health summary

Runtime Foundation, Market Intelligence, Decision Intelligence, Risk Construction, and
Execution Integration each report PASS, WARNING, or FAIL. The aggregate can PASS only when
every component and supplied validation report passes. WARNING is never promoted to aggregate
PASS. Any missing or inconsistent evidence results in FAIL and `READINESS_DENIED`.

## Authority

Certification is evidence, not activation. `production_authorized` is structurally false in
pipeline, delivery, runtime, readiness, and aggregate reports. V27 remains the sole production
authority until explicit human approval.
