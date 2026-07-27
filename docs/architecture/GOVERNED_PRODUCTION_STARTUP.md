# Governed production startup

## Boundary and prerequisite

`runtime.production_startup` is the operator-facing composition. It automatically
resolves the **exact PR184 Decision Intelligence identity bundle** from the sole
immutable owner-governed production-input activation record, invokes the existing
`GovernedDecisionRecommendationEngine` (PR185 owner), persists its deterministic
Recommendation through `DecisionRecommendationRepository`, and passes the returned
Recommendation UUID to PR209. It never chooses a latest record and never constructs
an identity.

PR185's canonical input is an immutable PR184 `DecisionIntelligence`, report, or
snapshot backed by its canonical repository and snapshot lineage. The activation binds
the exact intelligence UUID/digest, snapshot UUID/digest, repository digest, policy
UUID/digest/version, engine version, and its own activation UUID/digest. Missing,
duplicate, corrupt, or mismatched activation fails closed. Resolution never derives
authority from current repository contents, READY-state scanning, timestamps,
filename ordering, or latest-record selection. READY state alone never creates an
activation or defines production eligibility. Consequently, a machine with no PR184
or upstream records cannot truthfully create PR185; the startup
fails closed with `DECISION_INTELLIGENCE_MISSING`. “Clean production state” for this
entrypoint means the PR184 governed chain is present while PR185–PR190 repositories
may be absent. Creating synthetic upstream intelligence would violate Rules #019 and
#020 and is intentionally not implemented.

The default repositories are `learning_data/decision_intelligence`,
`learning_data/decision_recommendation`, `learning_data/execution_readiness`,
`learning_data/execution_environment`, `learning_data/execution_feasibility`, and
`learning_data/execution_package`.

## Governed observation collection

Startup samples the canonical MT5 `market_state.json` itself for five seconds before
constructing PR187 evidence. The immutable `PR187-OBSERVATION-POLICY.1.0` declares
each dimension's definition, source field, units, aggregation formula, threshold,
policy UUID/digest, and source provenance. Freshness is calculated exclusively from
the payload's `heartbeat_unix`; filesystem timestamps have no authority. Heartbeats
must not be future or older than five seconds, and at least three unique, strictly
increasing sequence/heartbeat pairs are required.

The source must identify itself as symbol `XAUUSD`, producer
`RP_AI_MT5_MARKET_STATE` version `V1`, telemetry schema `1.0`, and the policy-bound
source UUID. Session quality, liquidity quality, and slippage expectation are direct
producer observations; startup never manufactures them from quotes or spread. A
malformed atomic-replacement read is recorded but never counted as an independent
observation. Missing, mismatched, frozen, decreasing, partial, future, or stale
telemetry fails closed. The operator neither supplies nor edits observations.

The PR187.2.1 policy requires:

| Argument | Meaning | Ready range |
|---|---|---|
| `--feed-stability` | stable-feed fraction | 0.95–1.0 |
| `--price-stream-continuity` | continuous-price fraction | 0.99–1.0 |
| `--market-session-quality` | session-quality fraction | 0.8–1.0 |
| `--spread-quality` | observed spread, points | 0–50 |
| `--latency-quality` | observed latency, milliseconds | 0–250 |
| `--slippage-expectation` | expected slippage, points | 0–30 |
| `--market-liquidity-quality` | liquidity-quality fraction | 0.8–1.0 |
| `--environment-consistency` | consistency fraction | 0.8–1.0 |
| `--data-freshness` | data age, seconds | 0–5 |
| `--environment-completeness` | complete-observation fraction | 0.9–1.0 |

PR187 rejects missing, non-finite, negative, wrongly ordered, or wrongly typed
observations. Values outside the ready thresholds produce a non-ready environment,
and startup stops before PR188/Runtime. No metric has a readiness default.

## Single PowerShell production command

The installed governed `learning_data/decision_intelligence/activations` repository
supplies the sole owner-activated identity bundle. MT5 and the market-state sync must
already be running. The operator then executes exactly one command; no UUID, digest,
timestamp, metric, JSON edit, or manual package environment variable is used.

```powershell
cd D:\RP_AI_EA
python -m runtime.production_startup
```

PR208 imports and invokes
`bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine.run` when no
test/runtime callback is injected. Before import, it sets
`RP_EXECUTION_PACKAGE_UUID` to the exact PR190-consumed package identity. Expected
runtime markers include `RP AI Decision Engine ... started`, `RUNTIME_BRANCH=`,
`BASE_PATH =`, followed by decision writes (or the explicit market-state read-failed
loop output). `PACKAGE_MISSING` is not expected.
