# PR263 V28 Risk Construction

## Ownership

Risk Construction answers only **“Can the authorized decision be executed safely?”**
It consumes immutable Decision, Runtime, account, portfolio, quote, broker, symbol, and
execution-policy contracts. It does not read indicators, reconstruct Market Intelligence,
reconsider Decision merit, submit orders, or activate V28.

## Canonical units

| Field family | Canonical unit |
| --- | --- |
| entry, stop, target, `stop_distance_price`, slippage | symbol price |
| `stop_distance_points`, broker stop/freeze levels | points (`point_size`) |
| requested cap, risk/margin/exposure volumes, `approved_volume` | broker volume |
| risk budget, loss, drawdown, costs, monetary risk and margin | account currency |
| symbol, directional, overlap, correlation and portfolio exposure | account-currency notional |
| risk/capital fractions | fraction of equity in `[0, 1]` |

`SymbolSpecification` binds point, tick, tick value, contract size, volume bounds and
step, margin per volume, currencies, conversion identity/rate, observation time, and a
canonical replay identity to the Decision symbol. `ExecutableQuote` binds bid, ask,
timestamp, sequence, source, age, and maximum slippage. BUY uses ask; SELL uses bid.

## Dimensional construction

Monetary risk per volume is `(stop price distance / tick size * tick value per volume)`
plus spread, quote slippage allowance, commission, cost-model slippage, and other
governed costs. Risk-based volume divides the account-currency risk budget by that
monetary amount. Margin-based volume separately divides account-currency capital
allocation by margin required per volume. Exposure-based volume divides remaining
account-currency notional capacity by account-currency notional per volume.

The approved volume is the floor-to-step result of the minimum risk, margin, exposure,
broker maximum, and optional advisory requested-cap volumes. It is never rounded up.
Entry, stop, and target must already be exactly tick-representable; Risk Construction
rejects rather than repairs them. Reward/risk is net of all governed costs.

## Fail closed and lineage

Decision replay, Decision/Runtime/quote/broker/specification symbol and sequence,
execution and cost models, Runtime health/freshness, evaluation time, account freshness,
broker freshness, symbol-specification freshness, currencies, and every feasibility gate
must agree. Missing required data short-circuits to `DEFERRED` without invented zeros or
downstream validation. Every rejected or deferred plan has `approved_volume=0`, no
executable entry, and no Executor projection.

## ExecutionPlan and ExecutorContract

`V28.EXECUTION_PLAN.1.1` is immutable, policy-versioned, normalized, explained, and
SHA-256 replay-identified. An approved plan enforces BUY/SELL side relationships,
complete lineage and policy references, exact all-valid reason state, volume-step and
tick-size normalization, finite positive monetary risk and margin, and full replay
identity. `V28.EXECUTOR_CONTRACT.1.1` independently revalidates those execution-facing
invariants and binds plan replay, Decision replay, Runtime sequence, execution model,
policy, and its own replay identity. It exposes no order-submission API.

```json
{
  "schema_version": "V28.EXECUTION_PLAN.1.1",
  "symbol": "XAUUSD",
  "direction": "BUY",
  "executable_entry_price": 110.1,
  "approved_volume": 4.0,
  "protective_stop": 108.0,
  "target": 114.0,
  "stop_distance_price": 2.1,
  "stop_distance_points": 21.0,
  "monetary_risk_per_volume": 250.0,
  "margin_required_per_volume": 1000.0,
  "approval_status": "APPROVED",
  "execution_ready": true,
  "validation_reasons": ["ALL_RISK_CONSTRUCTION_CHECKS_VALID"]
}
```
