# CURRENT_SYSTEM_STATE — V26.4.7 Participation Restoration Program

Date: 2026-06-09 (UTC)
Authoritative branch policy: `codex-dev`

## Governance posture
- Single authoritative runtime lineage must be maintained on `codex-dev`.
- AI-room patch chains are reference inputs only and are not runtime authorities.
- Required promotion sequence: `AI ROOM -> CODEX MERGE -> codex-dev verification -> TEST -> LIVE promotion`.
- Architecture authority: V26.4.6 Recursive Participation Suppression Fix remains the baseline; V26.4.7 restores controlled participation on top of that authority.

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
