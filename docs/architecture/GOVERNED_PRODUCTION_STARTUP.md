# Governed production startup

## PR184 operator procedure

Production startup requires the following explicit, fail-closed operator sequence:

1. Construct PR184 Decision Intelligence through its owner engine.
2. Run the read-only inspection: `python -m learning.decision_intelligence.operator_inspection`
   (use `--format json` for canonical machine-readable evidence).
3. Review one exact intelligence/snapshot pair and its complete lineage evidence.
4. Record the human approval timestamp explicitly in UTC. Inspection does not infer it.
5. Run `python -m learning.decision_intelligence.operator_activation` with the exact
   reviewed intelligence UUID, snapshot UUID, owner authority, and approval timestamp.
6. Run `start_ai_runtime.ps1`.

An optional exact-pair `--approval-request-output` artifact remains
`PENDING_OPERATOR_APPROVAL`. The optional `--print-activation-command` mode requires
`--approved-at` and only prints a copyable command; it never executes activation.

**INSPECTION EVIDENCE != OPERATOR APPROVAL != CANONICAL ACTIVATION.** Inspection has no
production-selection, Runtime, strategy, trading, broker, order, position, exit, or
execution authority and never modifies the canonical PR184 repository.

## Boundary and prerequisite

PR184 construction and production activation are separate lifecycle steps. The
construction-only engine persists intelligence and snapshot evidence but grants no
activation. The retired `GovernedDecisionIntelligenceBootstrap` fails with
`ACTIVATION_REQUIRES_OPERATOR_COMMAND`; neither it nor Runtime may infer or create a
production selection. An owner explicitly commits exact intelligence and snapshot
UUIDs with `learning.decision_intelligence.operator_activation`.

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

## PR184 activation contract and validation

The canonical record is stored only at
`learning_data/decision_intelligence/activations/<activation_uuid>.json`. Its exact
schema is `PR184-DECISION-INTELLIGENCE-ACTIVATION.1.0` and its authority owner is
`PR184_DECISION_INTELLIGENCE_OWNER`. It contains `activation_state` (`READY` for a
committed production input), the explicit `activated_at` UTC timestamp, intelligence
UUID/digest, snapshot UUID/digest, repository digest, policy UUID/digest/version, and
engine version. `activation_uuid` is UUIDv5 over the canonical identity payload in
the PR184 activation namespace; `activation_digest` is SHA-256 over that payload plus
the UUID. The selection, owner, state, timestamp, compatibility, and lineage are
therefore immutable and reproducible.

Commit validates canonical source JSON, exact caller-selected UUIDs, intelligence
`DECISION_INTELLIGENCE_READY`, snapshot membership, repository digest, the complete
snapshot chain, and policy/engine compatibility before using an atomic append-only
link. An identical replay is idempotent; replacement or a second selection is
rejected. Startup independently validates schema, UUID, digest, owner, READY state,
canonical location/filename/JSON, exact lineage, and compatibility. Every rejection
uses a domain-specific reason; there is no repair or fallback.

The operator obtains the exact UUIDs from the approved PR184 construction report,
records the approval timestamp, and runs:

```powershell
python -m learning.decision_intelligence.operator_activation `
  --intelligence-uuid <approved-intelligence-uuid> `
  --snapshot-uuid <approved-snapshot-uuid> `
  --authority-owner PR184_DECISION_INTELLIGENCE_OWNER `
  --activated-at <approved-utc-timestamp>
```

Only after this command succeeds may the operator run production startup. No file
editing, directory scan, newest-record selection, hidden UUID, or Runtime bootstrap
is an activation procedure.

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

## PR248 fresh-install prerequisite

Production initialization does not bootstrap learning evidence. Before initialization,
use the governed PR248 inspection/plan/exact-construction workflow documented in
`PR248_END_TO_END_GOVERNED_BOOTSTRAP.md`. A fresh clone requires real external PR173
outcome evidence and a separately approved PR175 evidence envelope; empty directories,
test fixtures, inferred latest identities, automatic approval, and automatic activation
are invalid. PR248 verification is read-only and does not replace the existing explicit
PR184 activation or production startup gates.
