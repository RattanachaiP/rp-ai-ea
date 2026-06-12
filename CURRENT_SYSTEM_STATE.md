# CURRENT_SYSTEM_STATE — V26.6.2A No-Pause Adaptive Expectancy Fix

Date: 2026-06-12 (UTC)
Authoritative branch policy: `codex-dev`

## Governance posture
- Single authoritative runtime lineage must be maintained on `codex-dev`.
- AI-room patch chains are reference inputs only and are not runtime authorities.
- Required promotion sequence: `AI ROOM -> CODEX MERGE -> codex-dev verification -> TEST -> LIVE promotion`.
- Architecture authority: V26.4.6 Recursive Participation Suppression Fix remains the baseline; V26.4.8 restores controlled participation by forcing valid risk-payload construction before final validation.

## Current repository audit snapshot
- Active runtime engine file in repository: `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.
- No `bridge/ai_decision_engine_xauusd_live.py` runtime alias file exists yet.
- Runtime identity metadata is embedded and exported to `decision.json` on every write:
  - `runtime_branch`
  - `arch_version`
  - `build_tag`
  - `runtime_signature`

## V26.4.7 participation restoration state
- Weak NOVA trend-momentum vetoes are converted into confidence penalties when directional authority, payload validity, market freshness, and hard safety checks remain valid.
- `WAIT_VALID` is finite. A directional wait lifecycle tracks `wait_valid_cycles` and releases to `EXECUTE_CAUTIOUS` after `WAIT_TIMEOUT_CYCLES`.
- `TRANSITION_WAIT` is finite. Persistent weakening tracks `transition_decay_count` and auto-releases after `TRANSITION_WAIT_MAX_CYCLES` instead of becoming a permanent soft lock.
- Participation release fields now explain recovery decisions:
  - `participation_release`
  - `participation_release_reason`
  - `wait_valid_cycles`
  - `wait_timeout_cycles`
  - `transition_wait_max_cycles`
  - `transition_wait_released`

## Safety posture retained
Hard safety remains authoritative and was not downgraded:
- stale market-state protection
- payload/schema validation
- invalid market data protection
- abnormal spread / liquidity / broker freeze protection
- max realized loss cap and catastrophic hard-risk controls

## Deferred expectancy review
Participation restoration intentionally comes before scaling. Before increasing participation size/frequency, review:
- SL sizing
- break-even timing
- trailing behavior
- runner enablement
- profit protection
- average win vs. average loss

## V26.4.8 intent-to-payload execution fix
- Directional `TRADE` intent is now normalized through `construct_risk_payload_before_validation()` immediately before final payload validation.
- A BUY/SELL `TRADE` can no longer reach `validate_final_decision_payload()` with `SL=0` / `TP=0` when a positive `entry_price` / `bid` exists and no hard safety block is active.
- If SL/TP construction cannot be completed because entry context is missing, validation emits controlled `WAIT_VALID` with explicit `risk_payload_construction_reason` instead of silently publishing malformed execution payload.
- Weak NOVA trend momentum remains a confidence penalty path; directional bias, action, scores, and cautious scalp management are preserved when hard safety remains clear.
- Strong `TRANSITION+NORMAL` score dominance (`score_gap >= 4`) treats small RSI misses as `rsi_soft_penalty_only` and allows cautious scalp execution when MACD is not strongly opposite.
- Fast participation override now recognizes preserved BUY/SELL intent in TREND/TRANSITION NORMAL contexts instead of returning `FAST_PARTICIPATION_NOT_TRADE` as a contradiction to participation recovery.

## V26.5 execution quality core upgrade
- Runtime authority advances to `V26.5 | execution-quality-core-upgrade` while keeping `codex-dev` as the single authoritative lineage.
- Execution evaluation now requires `Direction + Entry Quality + Position Construction + Profit Extraction` instead of direction-only participation.
- `ENTRY_LOCATION_SCORE` is a first-class decision field. It rewards fresh breakout/walk context, healthy pullbacks, continuation return, and directional dominance; it penalizes exhaustion, extreme RSI, MA50 distance, BB overextension, late expansion entry, and reversal proximity.
- Poor entry location is treated as a finite quality wait (`WAIT_ENTRY_LOCATION` / `WAIT_VALID`) rather than a malformed or direction-erasing payload.
- Decision payloads now publish a directional idea with multi-leg construction metadata:
  - Leg A: Scout Entry / scalp profit bank.
  - Leg B: Confirmation Entry / pullback continuation participation.
  - Leg C: Continuation Entry / runner capture.
- Scaling policy is explicit: scale into winners only, no martingale, no averaging losers, and no buy+sell hedge architecture.
- Profit extraction metadata now includes a profit-lock ladder concept: +100 points lock +50, +200 lock +100, +300 lock +200.
- Trade-memory analysis now reports daily expectancy metrics: Win Rate, Average Win, Average Loss, Profit Factor, Expectancy, Average Holding Time, and Runner Capture Rate.

## V26.5 expectancy-structure repair
- Legacy quality paths that previously acted as hidden executor vetoes now defer to AI authority when `decision=TRADE`, bias/mode/BB/schema/heartbeat are valid, and hard safety is clear.
- M15/M3 misalignment and M3 timing conflicts are timing refinements with explicit confidence penalties instead of trade annihilation layers.
- NOVA and V17 entry-quality rejections are softened to penalty/audit fields under valid AI authority; only stale data, invalid payload/schema, abnormal spread/liquidity/freeze, duplicate protection, daily risk, and catastrophic risk remain hard final veto classes.
- Trend-walk management now preserves or upgrades runner intent: `TREND + WALK_UP/WALK_DOWN + score_gap >= 4` prefers `HOLD_TRAIL`, with `SCALP_TP` demoted to a secondary mode.
- Planned reward/risk is calculated and enforced before final payload validation: SCALP requires at least 1.2R, while TREND/runner structures require at least 1.5R.

## V26.6 expectancy repair program
- Runtime authority advances to `V26.6 | expectancy-repair-program` under the same `codex-dev` lineage.
- Trend management is now enforced after confidence recovery and final schema normalization: `MODE=TREND` may not publish `SCALP_TP` unless explicit downgrade metadata exists. Silent trend scalps are upgraded to `HOLD_TRAIL` or `TREND_RUNNER` to preserve asymmetric reward capture.
- Early participation is graded by score gap without increasing total risk: gap 2 publishes 25% risk, gap 3 publishes 50% risk, and gap 4+ publishes 100% risk through `risk_fraction` / `position_size_multiplier` fields.
- Loss compression metadata is published on every executable trade: planned SL risk points, max realized loss guard at 1.05R, risk budget fraction, and loss-compression policy fields.
- Late entry scoring now explicitly tracks RSI compression after expansion, BB overextension, MA50 distance, exhausted MACD expansion, and expansion candle count. High scores wait for location reset; elevated scores reduce size.
- Expectancy analytics now report Average R Win, Average R Loss, realized-vs-planned loss ratio, loss-over-plan count, and max loss vs plan in addition to daily expectancy metrics.

## V26.6.1 pre-merge governance safety review
- Runtime authority advances to `V26.6.1 | expectancy-emergency-repair` for protection-cascade control while preserving the V26.6 expectancy repair concept.
- `ACTIVE_PROTECTION_STATE` is now a required decision payload field managed by the Protection Authority Manager.
- Only one protection state may be `ACTIVE` at a time across `SESSION_PROFIT_PROTECTION`, `DAILY_PEAK_DRAWDOWN_PROTECTION`, `THESIS_REVALIDATION_AFTER_LOSS`, `THESIS_DECAY_WAIT`, `POST_RUNNER_COOLDOWN`, and `WAIT_ENTRY_LOCATION`; any additional detected protection becomes `PENDING` instead of stacking recursively.
- Every governed protection publishes an entry condition, exit condition, maximum duration, maximum cycles, and recovery path in `protection_states`.
- WAIT-like protections are finite: `THESIS_DECAY_WAIT` releases on directional recovery / timeout, and `WAIT_ENTRY_LOCATION` releases on location recovery / timeout to controlled cautious participation when directional authority remains valid.
- Monitoring fields now include `protection_activation_count`, `protection_duration_sec`, `protection_duration_cycles`, `opportunity_block_count`, `time_to_recovery_sec`, `protection_pending_states`, `protection_timeout_released`, and `protection_recovery_released`.
- The 72+ hour observation window must evaluate whether protection states improve expectancy or create participation starvation V2 by comparing protection metrics with expectancy, profit factor, average win/loss, and opportunity-block counts.

## V26.6.1 executor legacy-veto audit update
- Executor-side terminal authority is now explicitly constrained to hard safety only: stale decision, invalid payload/schema, abnormal spread or liquidity/freeze, duplicate order protection, and daily risk limit.
- Legacy V17 AI quality, V15 entry, `analysis_quality`, alignment, and participation gates are classified as `SOFT_DIAGNOSTIC_PENALTY` when AI authority is valid (`decision=TRADE`, BUY/SELL bias, schema/freshness valid, score edge present, and no hard safety block).
- The decision writer now publishes an executor authority contract in every payload: `ai_decision_authority`, `executor_authority_chain`, `executor_hard_block_scope`, and `legacy_executor_veto_policy`.
- For executable AI-authorized trades, raw legacy quality remains available as `analysis_quality_diagnostic` / `v17_quality_score_diagnostic`, while `analysis_quality` receives a V17 compatibility floor of `60` to prevent historical executor code from treating missing/zero quality as a terminal veto.
- `V17_AI_QUALITY_BLOCK` is no longer execution authority in the runtime payload contract. It is diagnostic telemetry only; the executor must proceed to broker safety checks and `OrderSend` when `decision=TRADE`, `allowed=true`, `entry_allowed=true`, and `payload_valid=true`.
- Runtime logs now emit `EXECUTOR AUTHORITY AUDIT` for executable trades, proving the AI emitted TRADE, the executor is expected to receive TRADE, legacy V15/V17 veto override is disallowed, and `OrderSend` is required after broker safety checks.

## V26.6.2 / V26.6.2A profit/loss asymmetry adaptive expectancy fix
- Runtime authority advances to `V26.6.2A | no-pause-adaptive-expectancy-fix`.
- Expectancy repair now treats distribution shape as the emergency: weak gap participation is disabled, loss size is compressed, and open profit is protected before trades can return to full loss.
- For reference size `0.01` lot XAUUSD, the decision payload publishes a hard realized-loss cap of `-$1.20`, a floating force-exit threshold as loss approaches the cap, and compresses new SL distance to the cap before final validation.
- Profit protection metadata is mandatory on TRADE payloads:
  - at `+$0.80` per `0.01` lot, move SL to breakeven plus spread;
  - at `+$1.20` per `0.01` lot, lock at least `+$0.50`.
- Signal expansion is explicitly not introduced. The fix reuses existing score, BB, RSI, MACD, trade-memory, and risk-payload fields only.
- Weak gap trades are disabled: `score_gap < 3` becomes `NO_TRADE`.
- `TRANSITION + NORMAL` now requires `score_gap >= 4`.
- Entries near BB middle are blocked unless RSI and MACD strongly confirm the intended direction.
- Trend-walk runner preservation remains authoritative: `MODE=TREND` with `WALK_UP` / `WALK_DOWN` continues to prefer `HOLD_TRAIL` / `TREND_RUNNER` unless existing explicit exhaustion or invalidation metadata appears.
- V26.6.2A supersedes pause behavior: loss clustering no longer creates a mandatory 30-minute pause; it publishes diagnostic telemetry, forces thesis revalidation, and applies adaptive size-down.
- V26.6.2A replaces the `<= -$5.00` daily kill switch with `DRAWDOWN_CAUTION_MODE`; new TRADE payloads may continue only as reduced-size Leg A with higher entry-location quality, while full stop is reserved for catastrophic hard-risk state.
- Measurement targets for this repair are: `Average Win >= +$1.20`, `Average Loss <= -$1.00`, and `Profit Factor > 1.30`.
