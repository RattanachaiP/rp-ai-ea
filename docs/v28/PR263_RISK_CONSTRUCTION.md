# PR263 V28 Risk Construction

## Ownership and contract

Risk Construction answers only **“Can the authorized decision be executed safely?”**
It consumes `DecisionContext`, `RuntimeContext`, `AccountState`, `PortfolioExposure`,
`ExecutionConstraints`, and `BrokerConstraints`. It does not read indicators, redo
Market Intelligence, reconsider the Decision, submit orders, or activate V28.

The orchestrator validates the Decision replay identity and execution-model binding,
Runtime freshness, account risk, position budget, portfolio concentration, protective
stop, target, reward/risk, volume, session, symbol, margin, stop, and freeze constraints.
Every input is explicit. A missing input produces `DEFERRED`; any failed validation
produces `REJECTED`; only a complete pass produces `APPROVED` and
`execution_ready=true`.

## ExecutionPlan schema

`V28.EXECUTION_PLAN.1.0` is an immutable, policy-versioned contract containing source
Decision replay identity, Runtime sequence, symbol, direction, volume, protective stop,
target, complete execution constraints, approval status, readiness, explanations, and
a deterministic SHA-256 replay identity. `V28.EXECUTOR_CONTRACT.1.0` is a narrow,
ready-only projection. It deliberately exposes no order-submission operation.

## Sample approved plan

```json
{
  "schema_version": "V28.EXECUTION_PLAN.1.0",
  "policy_version": "1.0.0",
  "symbol": "XAUUSD",
  "direction": "BUY",
  "volume": 1.0,
  "protective_stop": 108.0,
  "target": 114.0,
  "approval_status": "APPROVED",
  "execution_ready": true,
  "validation_reasons": ["ALL_RISK_CONSTRUCTION_CHECKS_VALID"]
}
```

The canonical plan also includes full constraints and lineage identities; they are
omitted above only to keep the illustrative excerpt readable.
