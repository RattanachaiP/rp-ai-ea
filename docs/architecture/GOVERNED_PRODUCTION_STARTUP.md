# Governed production startup

## Boundary and prerequisite

`runtime.production_startup` is the operator-facing composition. It resolves one
operator-supplied **exact PR184 Decision Intelligence identity bundle**, invokes the existing
`GovernedDecisionRecommendationEngine` (PR185 owner), persists its deterministic
Recommendation through `DecisionRecommendationRepository`, and passes the returned
Recommendation UUID to PR209. It never chooses a latest record and never constructs
an identity.

PR185's canonical input is an immutable PR184 `DecisionIntelligence`, report, or
snapshot backed by its canonical repository and snapshot lineage. Consequently, a
machine with no PR184 or upstream records cannot truthfully create PR185; the startup
fails closed with `DECISION_INTELLIGENCE_MISSING`. “Clean production state” for this
entrypoint means the PR184 governed chain is present while PR185–PR190 repositories
may be absent. Creating synthetic upstream intelligence would violate Rules #019 and
#020 and is intentionally not implemented.

The default repositories are `learning_data/decision_intelligence`,
`learning_data/decision_recommendation`, `learning_data/execution_readiness`,
`learning_data/execution_environment`, `learning_data/execution_feasibility`, and
`learning_data/execution_package`.

## Observation contract

Values are finite, non-negative floats captured from production monitoring at the
declared UTC timestamp. The PR187.2.1 policy requires:

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
and startup stops before PR188/Runtime. Operators must use measured values; the
command supplies no observation defaults.

## PowerShell operator command

Supply the UUID, digest, exact snapshot UUID/digest, repository digest, and policy
partition emitted together by the already-governed PR184 production process. None may
be invented or selected from repository ordering. The variables below represent that
single owner-emitted bundle.

```powershell
cd D:\RP_AI_EA
$DecisionIntelligenceUuid = Read-Host "Exact PR184 Decision Intelligence UUID"
$DecisionIntelligenceDigest = Read-Host "Exact PR184 Decision Intelligence digest"
$IntelligenceSnapshotUuid = Read-Host "Exact PR184 snapshot UUID"
$IntelligenceSnapshotDigest = Read-Host "Exact PR184 snapshot digest"
$IntelligenceRepositoryDigest = Read-Host "Exact PR184 repository digest"
$IntelligencePolicyUuid = Read-Host "Exact PR184 policy UUID"
$IntelligencePolicyDigest = Read-Host "Exact PR184 policy digest"
$IntelligencePolicyVersion = Read-Host "Exact PR184 policy version"
$IntelligenceEngineVersion = Read-Host "Exact PR184 engine version"
python -m runtime.production_startup `
  --decision-intelligence-uuid $DecisionIntelligenceUuid `
  --decision-intelligence-digest $DecisionIntelligenceDigest `
  --decision-intelligence-snapshot-uuid $IntelligenceSnapshotUuid `
  --decision-intelligence-snapshot-digest $IntelligenceSnapshotDigest `
  --decision-intelligence-repository-digest $IntelligenceRepositoryDigest `
  --intelligence-policy-uuid $IntelligencePolicyUuid `
  --intelligence-policy-digest $IntelligencePolicyDigest `
  --intelligence-policy-version $IntelligencePolicyVersion `
  --intelligence-engine-version $IntelligenceEngineVersion `
  --captured-at "2026-07-27T12:00:00Z" `
  --feed-stability 0.99 `
  --price-stream-continuity 0.999 `
  --market-session-quality 0.90 `
  --spread-quality 20.0 `
  --latency-quality 100.0 `
  --slippage-expectation 10.0 `
  --market-liquidity-quality 0.90 `
  --environment-consistency 0.90 `
  --data-freshness 2.0 `
  --environment-completeness 0.95
```

PR208 imports and invokes
`bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine.run` when no
test/runtime callback is injected. Before import, it sets
`RP_EXECUTION_PACKAGE_UUID` to the exact PR190-consumed package identity. Expected
runtime markers include `RP AI Decision Engine ... started`, `RUNTIME_BRANCH=`,
`BASE_PATH =`, followed by decision writes (or the explicit market-state read-failed
loop output). `PACKAGE_MISSING` is not expected.
