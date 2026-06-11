# CURRENT_SYSTEM_STATE — V26.4.8 Intent-to-Payload Execution Fix

Date: 2026-06-09 (UTC)
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
- daily-loss and hard-risk controls

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

## V26.6.1 expectancy emergency repair
- Runtime authority remains `V26.6 | expectancy-repair-program`; patch level V26.6.1 adds realized trade-distribution protections without adding indicators, classifiers, or infrastructure layers.
- `MAX_REALIZED_LOSS_GUARD` now publishes planned-vs-realized loss discipline fields on every decision path: `planned_R`, `planned_loss_r`, `planned_sl_risk_points`, `realized_R`, `max_realized_loss_r`, `loss_over_plan_count`, `realized_planned_loss_ratio`, and `max_loss_over_plan`.
- Learning/trade-result ingestion now tracks `planned_R` and `realized_R` from `trade_results.jsonl` / `trade_results.json`, including loss-over-plan counts, cumulative realized/planned loss ratio, max loss over plan, consecutive losses, and last trade R.
- If `consecutive_losses >= 2`, participation pauses for 20 minutes through `LOSS_CLUSTER_PAUSE` to prevent grouped loss clusters.
- If the last closed trade realizes at least `2R` or a major runner is captured, participation cools down for 12 minutes through `POST_RUNNER_COOLDOWN` to avoid immediate exhausted trend re-entry.
- The guard tracks `daily_peak_profit`; if the current day gives back at least 50% of the peak or at least 2.50 profit units, it activates `SESSION_PROFIT_PROTECTION` for the session protection window.
- Failed continuation attempts decay same-direction conviction. After repeated failed BUY or SELL continuations, same-side participation is reduced to 25% risk or paused through `THESIS_DECAY_WAIT` when score authority is not strong enough.
- Existing RSI, MA50 distance, BB maturity/overextension, MACD expansion, candle expansion, and trend/exhaustion scores continue to drive mature-entry handling: elevated exhaustion reduces size; high exhaustion forces `WAIT_ENTRY_LOCATION`.
