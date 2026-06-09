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
