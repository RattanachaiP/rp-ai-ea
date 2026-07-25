# DECISION_FLOW_MAP — Runtime Lineage and Participation Governance Flow

## Authoritative lineage
`codex-dev` (single source of truth)

## V28 decision-rebuild approval flow (proposal only)

`Market -> Opportunity -> Positive Edge Verification -> Decision -> Risk -> Publish`

The first and controlling question is: **Does this opportunity have positive
expectancy?** Direction is selected only after the positive-edge verification
passes. `docs/v28/V28_DECISION_PHILOSOPHY.md` and
`docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md` define the required
opportunity, positive-edge, evidence, decision-lineage, and approval contract.

This is not an active runtime path. No implementation work is authorized until
the philosophy document receives explicit approval. V27 remains the current
runtime path below; no V27 filters, cooldowns, waits, score adjustments, patch
stacks, or runtime layers may be added under this directive.

## Governance flow
1. AI room proposes reference patch
2. Codex merges into authoritative code review stream
3. `codex-dev` verification
4. Test validation
5. Approved LIVE promotion

## PR169 rollback orchestration flow
`Runtime Health / Rollback Request`
-> `learning.rollback_orchestration` request, UUID, lineage, manifest, compatibility, and snapshot validation
-> `MANUAL_ONLY` human approval
-> deterministic rollback decision, authorization, plan, package, and append-only audit evidence
-> `Controlled Activation` (outside PR169 authority)
-> registry snapshot and immutable KnowledgeVersion (outside PR169 authority).

PR169 has no Runtime, broker, registry, activation, promotion, or version-mutation capability.

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
- catastrophic daily risk limit / hard realized-loss control
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

`THESIS_REVALIDATION_AFTER_LOSS -> THESIS_DECAY_WAIT -> WAIT_ENTRY_LOCATION -> POST_RUNNER_COOLDOWN -> NO PARTICIPATION`

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

## V26.6.5A executor authority enforcement hotfix
The restored single execution authority chain is:

`AI Decision`
-> `Payload Validation`
-> `Broker Safety`
-> `OrderSend`
-> `Market`

If `decision=TRADE`, `allowed=true`, `payload_valid=true`, and `schema_valid=true`, the executor must not allow legacy strategy filters to terminate execution. V15/V16/V17 entry, AI-quality, hard-block, and M15/M3 alignment findings remain visible as warnings/diagnostics, but they do not own execution authority and may not suppress `OrderSend`.

Only these classes may terminate execution after an AI-approved payload: invalid payload, invalid schema, stale decision, broker freeze, abnormal spread, duplicate order, insufficient margin, market closed, and catastrophic risk state. A validated TRADE that does not call `OrderSend` must emit `EXECUTOR_BUG_NO_ORDERSEND_AFTER_TRADE`. Normal send path logs are `EXECUTOR_FINAL_GATE_PASS`, `ORDER_SEND_ATTEMPT`, and exactly one of `ORDER_SEND_OK` / `ORDER_SEND_FAIL`.

## V26.6.2A no-pause adaptive expectancy flow update
The final write path now includes an emergency expectancy-distribution guard:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> trend management preservation (`TREND + WALK_UP/WALK_DOWN` prefers `HOLD_TRAIL` / `TREND_RUNNER`)
-> `V26.6.2_EXPECTANCY_ENTRY_FILTER`
-> `V26.6.2A_SESSION_LOSS_GOVERNOR` (loss diagnosis + adaptive risk reduction; no mandatory pause)
-> risk payload construction
-> `V26.6.2_LOSS_CAP_AND_PROFIT_LOCK`
-> planned RR enforcement
-> final payload validation
-> executor hard-safety contract.

Emergency distribution rules:
- `score_gap < 3` is `NO_TRADE`.
- `TRANSITION + NORMAL` requires `score_gap >= 4`.
- BB-middle entries require strong RSI and MACD confirmation in the trade direction.
- For `0.01` lot XAUUSD, new TRADE payloads publish `max_realized_loss_usd_001_lot = 1.20` and compress SL distance to that reference cap.
- If floating loss approaches the cap, executor-side trade management should force exit using the published `floating_force_exit_usd_001_lot` / `floating_force_exit_points` fields.
- If profit reaches `+$0.80`, executor-side trade management should move SL to breakeven plus spread using the published breakeven ladder fields.
- If profit reaches `+$1.20`, executor-side trade management should lock at least `+$0.50` using the published lock ladder fields.
- After every loss, classify the loss cause: `LATE_ENTRY`, `EXHAUSTION_ENTRY`, `CHOP_ENTRY`, `REVERSAL_ENTRY`, `SL_TOO_WIDE`, `BE_TOO_TIGHT`, `TREND_THESIS_FAILED`, or `EXECUTOR_MANAGEMENT_FAILURE`.
- Two consecutive losses no longer trigger a mandatory pause. Loss clusters are diagnostic telemetry that trigger thesis revalidation and adaptive size-down.
- Same-direction repeated losses re-check bias, mode, BB state, RSI/MACD context, entry location score, and exhaustion score. Valid thesis continues cautiously; invalid thesis waits for better location or evaluates the opposite thesis.
- After a loss cluster, next participation is reduced-risk Leg A only: no runner, no pyramid, no runner add, no continuation add, and tighter risk cap.
- Current-day drawdown beyond threshold activates `DRAWDOWN_CAUTION_MODE`, not a daily kill switch: reduced size, Leg A only, higher entry-location score, no runner add, and no continuation add. Full stop is reserved for catastrophic hard-risk state.

This layer does not add indicators and does not bypass hard safety. Its purpose is to transform realized expectancy from many small wins plus larger losses into moderate wins plus controlled losses while keeping AI learning and participating with reduced risk.

## V26.6.3 exit / risk asymmetry emergency flow update
The final write path keeps the existing entry engine and adds an exit-first risk asymmetry layer:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> unchanged V26.6.2 expectancy entry filters
-> `V26.6.3_EXIT_RISK_ASYMMETRY_GOVERNOR`
-> risk payload construction
-> hard loss cap / early damage cut / breakeven ladder / profit lock ladder
-> runner damage limit and 30-45 second runner momentum timeout metadata
-> daily emergency risk stop at `<= -$5.00`
-> three-loss extreme caution mode
-> final payload validation
-> executor hard-safety contract.

This update does not add indicators, redesign signal generation, introduce hedging, martingale, or average losing trades. It changes position lifecycle enforcement so big realized losses below `-$2.00` should approach zero under standard `0.01` lot operation.

## V26.6.4 exit authority / leg-aware profit protection flow update
The final write path now ends with an executor-enforceable exit authority manager:

`payload validation / risk construction`
-> `hard loss cap + leg-aware profit ladder publication`
-> `single Exit Authority Manager`
-> `management authority lock`
-> `executor authority contract`
-> `decision.json`.

Exit authority priority is fixed and non-recursive:
`EMERGENCY_EXIT -> HARD_LOSS_CAP -> DAILY_GUARD_RISK_COMPRESSION -> FORCE_SCALP_TP -> LEG_A_SCALP_EXIT -> LEG_B_CONFIRMATION_EXIT -> LEG_C_RUNNER_EXIT`.

If `FORCE_SCALP_TP` owns a position, all downstream fields must treat management as `SCALP_TP`; runner/trail management cannot reactivate underneath that owner. Leg A and Leg B use distinct USD-per-0.01-lot ladders, while Leg C preserves runner intent through structure trail, momentum decay, swing protection, and BB-walk continuity. Daily Guard compresses risk and blocks new entries without converting open losing positions into arbitrary panic closes.

## V26.6.5 execution timing flow update
The final write path now separates directional thesis from executable timing:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> `V26.6.5_EXECUTION_TIMING_LAYER`
-> `ENTRY_WINDOW_SCORE` / `WAIT_ENTRY_WINDOW` or open entry window
-> risk payload construction
-> exit authority / payload validation
-> executor hard-safety contract.

The timing layer is not a new directional classifier. It reuses existing short-term candle/structure/BB/RSI/MACD/pullback/continuation telemetry. If HTF bias is BUY while short-term state shows bearish impulse, lower-high/lower-low structure, BB walk down, negative MACD expansion, or weak RSI recovery, the payload preserves BUY bias but waits with `WAIT_ENTRY_WINDOW`. SELL is handled by mirrored logic. Entry reopens when short-term phase transitions from `PULLBACK` to `RESUMPTION` / `TREND_EXPANSION` through recovery evidence such as pullback maturity, momentum improvement, continuation quality, and BB-walk ending/aligning.

## V26.6.6 expectancy diagnostic + exhaustion / protection flow update
The final write path now adds diagnostic and protective expectancy controls without reducing the normal signal cadence:

`real BUY/SELL signal`
-> `shadow opposite-direction audit record (non-live)`
-> existing execution timing / location scoring
-> `V26.6.6_EXHAUSTION_PROTECTION` (`WAIT_ENTRY_WINDOW`, reduced size, no-runner scalp-only, or allow)
-> `same-direction loss-chain direction pause` (pause losing direction only after 3 losses)
-> `profit protection publication` (`+$0.50` BE, `+$0.80` small-profit lock)
-> `runner allowed only after primary leg protected`
-> executor authority contract.

The shadow audit answers whether loss clusters are caused by wrong direction or by poor timing/exit management. It is telemetry only and cannot place opposite live trades.

## V26.6.7 trade autopsy evidence flow update
Closed-trade analytics now run after execution and do not feed back into live entry or exit authority:

`closed RP trade in trade_memory.csv`
-> `TRADE AUTOPSY ENGINE`
-> one CSV row per closed trade with identity, entry context, exit context, MFE/MAE, realized R, profit give-back, shadow-opposite audit, and evidence fields
-> daily JSON summary with win/loss distribution, expectancy, MFE capture, MAE containment, shadow-opposite result, and root-cause ranking by capital damage.

The autopsy engine is evidence-only. It cannot publish live trade decisions, cannot place opposite trades, cannot reduce entry frequency, cannot add indicators, and cannot change executor or exit authority. Its only purpose is to identify which loss bucket is causing the largest capital damage after 100-300 closed trades.

## V27 trade management dashboard flow update
The runtime is now split into independent subsystems:

`AI Decision Engine`
-> direction / bias / entry timing / market mode / position classification / initial risk
-> `POSITION CREATED`
-> `Trade Management Dashboard runtime profile load`
-> dashboard-configured SL, breakeven, trailing, profit-lock, runner, time-exit, partial-exit parameters
-> `Exit Authority Manager`
-> single effective exit owner
-> broker / executor.

Dashboard profile loading order:
1. Load embedded backward-compatible defaults.
2. Load `trade_management_dashboard.json` if present.
3. Resolve `active_profile`.
4. Overlay `dashboard_profiles/<active_profile>.json` if present.
5. Publish `trade_management_dashboard`, `dashboard_active_profile`, schema version, and source/fallback metadata to `decision.json`.

No V27 dashboard profile may mutate AI direction, bias, entry timing, signal generation, or market classification.

## PR173 outcome attribution flow

`Immutable Runtime / Learning Evidence` -> `learning.outcome_attribution` -> offline deterministic, advisory-only descriptive feature, indicator, risk, regime, context, success/failure, and sample-support attribution -> immutable report. This is non-causal analytical evidence and has no Runtime, Registry, promotion, activation, rollback, or execution authority. `learning.analytics` separately retains lineage, conflict, stability, and governance analytics authority.

## PR173 / PR174 offline eligibility flow
`Immutable evidence -> PR173 outcome attribution -> PR174 structural validation, identity/outcome/replay gates, and sample sufficiency -> immutable advisory eligibility report -> potential future offline pattern-mining stage.` PR174 performs no mining, learning, promotion, activation, registry, runtime, or broker action.

## PR175 offline pattern-mining flow

`PR174 eligible policy report + immutable ApprovedPatternMiningEvidenceEnvelope -> provenance and evidence integrity validation -> normalized offline grouping -> deterministic advisory CandidatePattern artifacts -> append-only PatternMiningReport -> future PR176 Pattern Memory.` PR175 consumes approved evidence only and never creates or modifies evidence. It has no learning, promotion, activation, Registry, Runtime, decision-publication, broker, or execution authority.
