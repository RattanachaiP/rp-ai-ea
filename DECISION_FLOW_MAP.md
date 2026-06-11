# DECISION_FLOW_MAP — Runtime Lineage and Participation Governance Flow

## Authoritative lineage
`codex-dev` (single source of truth)

## Governance flow
1. AI room proposes reference patch
2. Codex merges into authoritative code review stream
3. `codex-dev` verification
4. Test validation
5. Approved LIVE promotion

## Runtime execution path (current)
`bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`
-> reads `market_state.json`
-> builds directional decision payload
-> applies entry-quality / NOVA / candle / exhaustion / structure / timing / location layers
-> applies V26.4.7 participation restoration
-> applies compatibility/validation layers
-> injects runtime identity metadata
-> atomically writes `decision.json`

## V26.4.7 directional authority chain
1. Hard safety blocks remain final authority.
2. Valid directional bias and score context are preserved through governance layers.
3. Weak momentum becomes a confidence penalty rather than a hard directional erase.
4. Cooldown, low-confidence, and timing waits are represented as finite `WAIT_VALID` recovery states.
5. `WAIT_VALID` timeout releases controlled participation through `EXECUTE_CAUTIOUS`.
6. `TRANSITION_WAIT` has a maximum duration and releases instead of recursively suppressing.
7. Final payload normalization preserves one outcome chain: safety block, finite wait, cautious execution, normal execution, or aggressive execution.

## Migration target (deferred-safe path)
Target file name: `bridge/ai_decision_engine_xauusd_live.py`

Recommended safe migration sequence:
1. Introduce `ai_decision_engine_xauusd_live.py` as thin launcher importing current runtime module.
2. Verify parity in decision outputs and startup identity logs.
3. Update operational launch scripts to point to `_live.py`.
4. Keep previous file as rollback reference until burn-in window passes.

## V26.4.8 intent-to-payload flow update
Final write normalization now includes an explicit intent-to-payload bridge:

`directional ACTION/BIAS`
-> hard-safety check
-> `construct_risk_payload_before_validation()`
-> final payload validation
-> executable `TRADE` or explicit `WAIT_VALID` / hard-safety block

This guarantees controlled participation packets are built before validation, not after validation has already downgraded them.

## V26.5 execution-quality flow update
Directional ideas now pass through an execution-quality core before final confidence and payload validation:

`directional ACTION/BIAS`
-> `ENTRY_LOCATION_SCORE`
-> `directional idea + execution legs`
-> `profit lock ladder metadata`
-> execution confidence
-> risk payload construction
-> final validation
-> executable `TRADE` or explicit quality wait.

The quality core is not a new indicator layer. It reuses existing PA/structure/SR/BB/RSI/MACD/timing fields to answer the execution question: `Is this location still worth entering?`

Leg governance remains one-directional only:
- Leg A scouts the idea.
- Leg B may participate only after pullback/continuation quality improves.
- Leg C is reserved for runner-quality trend expansion.
- All scaling is winner-only; martingale, averaging losers, and hedge architecture remain prohibited.

## V26.5 expectancy-structure repair update
The execution chain is now audited as an authority map, not just a participation map:

`AI DECISION`
-> schema/time/freshness validation
-> entry-quality/NOVA/candle/exhaustion/structure/timing/location scoring
-> legacy strategy blocks converted to confidence penalties when AI authority is valid
-> management alignment and planned RR enforcement
-> final payload validation
-> broker/executor hard safety checks
-> `FINAL ORDER AUTHORITY`.

AI authority is valid only when `decision=TRADE`, bias is BUY/SELL, mode and BB state are schema-valid, heartbeat/market freshness are valid, score edge exists, and no hard safety block is active. In that state, legacy M15/M3 misalignment, M3 timing conflict, NOVA quality rejection, and V17 entry-quality rejection are no longer automatic executor vetoes; they are published as confidence penalties and audit fields.

Final hard veto authority is intentionally limited to:
- stale market data / heartbeat failure
- invalid JSON or invalid schema
- invalid market data
- abnormal spread / liquidity / broker freeze
- duplicate order protection
- daily risk limit / daily loss
- catastrophic hard-risk state

Expectancy structure is enforced before publishing a TRADE payload. SCALP structures must plan at least 1.2R; TREND and runner structures must plan at least 1.5R. TREND + `WALK_UP` / `WALK_DOWN` with score-gap authority prefers `HOLD_TRAIL` instead of silently downgrading into `SCALP_TP`; `SCALP_TP` remains a secondary management mode.

## V26.6 expectancy-repair flow update
The final write path now prioritizes expectancy before signal count:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> weak-momentum confidence penalty only when hard safety is clear
-> `LATE_ENTRY_SCORE` maturity audit
-> execution confidence
-> trend management enforcement (`TREND` cannot silently publish `SCALP_TP`)
-> graded early participation sizing (`gap=2/3/4` => `25%/50%/100%` risk)
-> risk payload construction and planned RR enforcement
-> `MAX_REALIZED_LOSS_GUARD` metadata
-> final validation
-> executable trade, reduced-size mature-entry trade, or `WAIT_ENTRY_LOCATION`.

This flow keeps existing indicators and classifier structure. It changes execution governance so optimization is measured by expectancy, Average R Win/Loss, runner capture, and realized-vs-planned loss discipline instead of raw signal count.

## V26.6.1 protection-authority flow update
The expectancy repair chain now includes a single protection authority before final payload construction:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> finite WAIT / cooldown / location protection candidates
-> `Protection Authority Manager`
-> exactly one `ACTIVE_PROTECTION_STATE`; other detected protections are `PENDING`
-> mandatory release metadata (`entry_condition`, `exit_condition`, `maximum_duration`, `maximum_cycles`, `recovery_path`)
-> risk payload construction and final validation
-> executable trade, released cautious participation, or one finite active protection.

This prevents the prior cascade pattern:

`LOSS_CLUSTER_PAUSE -> THESIS_DECAY_WAIT -> WAIT_ENTRY_LOCATION -> POST_RUNNER_COOLDOWN -> NO PARTICIPATION`

from becoming recursive. The manager does not remove hard safety; it prevents multiple quality/profit/cooldown protections from all being simultaneously active and unbounded.

## V26.6.1 executor legacy-veto conflict audit update
The single execution authority chain is now:

`AI Decision`
-> `Payload Validation`
-> `Executor broker-safety checks only`
-> `Market / OrderSend`

Executor-side veto classification:
- `HARD_SAFETY_BLOCK`: stale decision, invalid payload, invalid schema, abnormal spread, no liquidity, broker freeze, duplicate order protection, daily risk limit.
- `SOFT_DIAGNOSTIC_PENALTY`: V17 AI quality block, V15 entry block, `analysis_quality` filters, M15/M3 alignment vetoes, legacy participation/cooldown/location/quality gates.

When `decision=TRADE`, `allowed=true`, `entry_allowed=true`, `payload_valid=true`, BUY/SELL bias is valid, and no hard safety block is active, no legacy quality gate may convert the payload to `NO_TRADE`. Legacy quality values remain visible as telemetry (`analysis_quality_diagnostic`, `v17_quality_score_diagnostic`, `legacy_executor_veto_policy`) and may reduce confidence, but they do not override V26 execution authority.
