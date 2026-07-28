# PR262 V28 Decision Intelligence

## Architecture and ownership

PR261 continues to own `OpportunityContext`. It remains advisory and always carries
`executable=false`. PR262 neither replaces nor mutates it. A separately owned, immutable
`ExpectancyEvidenceRecord` carries canonical historical evidence. PR262 binds that record
and the current opportunity into a `DecisionCandidate`; candidate authorization is not
broker or execution authority.

The evidence contract binds source authority, symbol, timeframe, archetype, market side,
regime, Market policy, execution and cost models, sample period, outcome distribution,
method, quality, recency, and expiry. Its evidence ID and replay identity are derived from
all canonical content and verified at construction and use.

## Governance gates

Expectancy requires exact current-scope matching plus costs, slippage, duplicate exclusion,
a minimum 90-day/100-observation sample, out-of-sample evidence, current/unexpired status,
a supported bootstrap method, a positive lower confidence bound, dispersion, drawdown, and
sample-scope consistency. Missing or mismatched evidence fails closed.

Confidence is categorical (`GOVERNED_EVIDENCE_SUFFICIENT` or
`GOVERNED_EVIDENCE_INSUFFICIENT`) and retains the governed evidence confidence measure; it
does not average duplicated scores. `DecisionRiskPrecheck` reports only whether the
candidate is `RISK_REVIEW_READY`. It does not claim stop, exposure, budget, broker, or full
risk eligibility.

Direction is authorized by the intersection of opportunity archetype, market-side scope,
and the evidence record's historical direction profile. Market side alone never creates an
action.

## DecisionContext and replay

`DecisionContext` is immutable `V28.DECISION_CONTEXT.1.1`. Its own validator rejects BUY or
SELL unless expectancy is positive, the risk precheck is ready, categorical confidence is
sufficient, lineage is complete, and the candidate is authorized for the same direction.
The replay identity hashes the complete canonical decision—nested expectancy, confidence,
risk precheck, candidate, lineage, explanations, evidence summaries, policy references,
and schema/policy versions—excluding only the replay identity itself.

## Diagnostic examples

```text
DECISION_INTELLIGENCE decision=BUY candidate=AUTHORIZED expectancy=POSITIVE_EXPECTANCY risk_precheck=RISK_REVIEW_READY confidence=GOVERNED_EVIDENCE_SUFFICIENT
DECISION_INTELLIGENCE decision=SELL candidate=AUTHORIZED expectancy=POSITIVE_EXPECTANCY risk_precheck=RISK_REVIEW_READY confidence=GOVERNED_EVIDENCE_SUFFICIENT
DECISION_INTELLIGENCE decision=HOLD candidate=UNAUTHORIZED expectancy=EXPECTANCY_NOT_ESTABLISHED risk_precheck=DECISION_RISK_PRECHECK_REJECTED
```

These are deterministic diagnostics, not production logs. PR262 has no raw-indicator,
publisher, Executor, broker, order, sizing, activation, learning, or runtime authority.
