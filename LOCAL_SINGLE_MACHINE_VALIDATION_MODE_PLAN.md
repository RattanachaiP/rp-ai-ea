# LOCAL_SINGLE_MACHINE_VALIDATION_MODE_PLAN

Date: 2026-05-24 (UTC)
Scope: Temporary infrastructure-isolation validation mode

## Objective
Temporarily run the full AI + MT5 execution loop on one PC to isolate distributed-bridge variables and validate execution lifecycle integrity.

This plan does **not** change strategy logic, indicators, classifier set, or expectancy tuning.

---

## 0) Preconditions and Safety Guardrails

- Keep branch governance unchanged (`codex-dev` remains authoritative runtime lineage).  
- Keep current runtime engine file unchanged: `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.  
- Use a dedicated local shared folder:
  - `D:\RP_AI_EA\shared\XAUUSD\`
- Required files in that folder:
  - `market_state.json`
  - `decision.json`
- Ensure MT5 AutoTrading state matches your test policy before starting.
- Preserve backups of current VPS/distributed scripts before disabling them.

---

## 1) Run MT5 Locally on PC

Checklist:
1. Close any RDP-mounted MT5 session references (if previously used).
2. Launch local MT5 terminal directly on the PC (not through VPS bridge path).
3. Open target chart/symbol/timeframe used by Writer and Executor EAs.
4. Confirm local terminal is receiving live ticks.
5. Confirm MT5 journal has no startup filesystem permission errors.

Pass criteria:
- Local MT5 chart updates in real time.
- Journal has no recurring file-write permission failures.

---

## 2) Attach Market State Writer EA Locally

Checklist:
1. Attach the Market State Writer EA to the intended local chart.
2. In EA inputs, set output path to:
   - `D:\RP_AI_EA\shared\XAUUSD\market_state.json`
3. Enable required permissions (DLL/file operations only if your EA requires them).
4. Verify EA init succeeds in Journal/Experts tab.

Pass criteria:
- `market_state.json` is created/updated by local MT5 only.
- No repeated file lock/permission errors.

---

## 3) Attach AI Executor EA Locally

Checklist:
1. Attach AI Executor EA to the local execution chart.
2. In EA inputs, set decision input path to:
   - `D:\RP_AI_EA\shared\XAUUSD\decision.json`
3. Verify symbol mapping and magic/order filters match your test setup.
4. Confirm EA init and timer/tick loop starts without errors.

Pass criteria:
- Executor reads `decision.json` locally.
- No bridge/network path dependency appears in logs.

---

## 4) Point Python AI to Local Shared Folder

Checklist:
1. Stop any existing AI process first.
2. Configure runtime file paths to local shared folder:
   - Read: `D:\RP_AI_EA\shared\XAUUSD\market_state.json`
   - Write: `D:\RP_AI_EA\shared\XAUUSD\decision.json`
3. Start AI runtime from repository runtime path.
4. Confirm startup logs show expected runtime identity metadata and local file targets.

Pass criteria:
- AI repeatedly ingests local `market_state.json`.
- AI writes local `decision.json` atomically with no permission contention.

---

## 5) Verify `market_state.json` Local Update Health

Checklist:
1. Observe file `modified timestamp` for at least 10-15 minutes.
2. Confirm timestamp advances consistently with Writer cycle.
3. Inspect payload fields for continuity:
   - `heartbeat_unix`
   - `sequence_id`
4. Confirm no stale freeze windows (timestamp not advancing while market is active).

Pass criteria:
- Stable write cadence.
- Monotonic/continuous heartbeat and sequence progression within expected runtime behavior.

---

## 6) Verify `decision.json` Local Update Health

Checklist:
1. Observe `decision.json` modified timestamp for 10-15 minutes.
2. Confirm decision payload refreshes as AI loop runs.
3. Validate continuity fields:
   - `decision_heartbeat_unix`
   - `sequence_id`
4. Validate quality/stability fields:
   - `decision_age_sec`
   - `execution_state`
   - `payload_validation_failed`
5. Confirm SL/TP field integrity on actionable decisions.

Pass criteria:
- Decision payload updates without gaps caused by sync/bridge contention.
- No malformed payload cycles.

---

## 7) Confirm Heartbeat + Sequence Continuity

Minimum observation window: 30 minutes (prefer 60+).

Track concurrently:
- `heartbeat_unix` (market state)
- `decision_heartbeat_unix` (AI decision)
- `sequence_id` in both files

Validation goals:
- No backward jumps.
- No long unexplained stalls while ticks are active.
- No repeated reset loops caused by file race conditions.

---

## 8) Ensure Legacy VPS Sync Processes Are Disabled

Checklist:
1. Stop scheduled/manual sync scripts tied to distributed mode, including:
   - `sync_decision_to_vps.ps1`
   - `bridge_sync/sync_market_state_to_pc_FORCE_ALWAYS_ATOMIC_FIX.ps1`
   - `bridge_sync/sync_decision_from_pc_FORCE_ALWAYS_ATOMIC.ps1`
2. Confirm no PowerShell background jobs are still moving these files.
3. Confirm no RDP `tsclient` redirected path is used by current MT5/AI config.
4. Confirm file activity on shared JSONs is only from local MT5 + local AI.

Pass criteria:
- No active sync/file-copy loops.
- No distributed bridge writes to local validation files.

---

## 9) Log Collection Package for Debug Room

Collect during each validation run:
1. MT5 Experts log slice (Writer + Executor period).
2. MT5 Journal log slice (same window).
3. AI runtime stdout/stderr logs.
4. Snapshots of `market_state.json` and `decision.json` at:
   - run start
   - midpoint
   - incident moment (if any)
   - run end
5. Incident timeline table with UTC timestamps:
   - symptom
   - observed file timestamp
   - heartbeat values
   - sequence_id values
   - execution_state

Naming convention (example):
- `local_validation_YYYYMMDD_HHMM_UTC/`

---

## 10) Rollback Plan to Distributed VPS Architecture (Later)

Rollback is allowed only after local validation conclusion is documented.

Steps:
1. Freeze local test run and archive logs.
2. Restore previous distributed path settings in Writer/Executor/AI configs.
3. Re-enable sync scripts one-by-one (not all at once).
4. Validate file propagation in sequence:
   - market state upstream path
   - decision downstream path
5. Re-check lock/contention symptoms after each script restore.
6. Keep a fast toggle checklist for switching back to local mode if contention returns.

---

## Validation Metrics Dashboard (What to Watch)

During Local Single-Machine Mode, monitor and annotate:
- `decision_age_sec` stability
- `heartbeat_unix` continuity
- `decision_heartbeat_unix` continuity
- `sequence_id` continuity
- cooldown lifecycle behavior
- WAIT vs NO_TRADE behavior
- `execution_state` distribution
- `payload_validation_failed`
- SL/TP integrity
- absence of `WinError 5`
- absence of sync-related file lock contention

---

## Exit Criteria for This Phase

Declare local validation phase complete when:
1. You have at least one clean observation window (>=60 minutes) with no sync/locking anomalies.
2. Continuity metrics remain stable across market-active periods.
3. Any remaining anomalies are attributable to decision logic behavior rather than distributed file transport.

Decision gate:
- If local mode is stable but behavior is weak -> bottleneck leans **AI execution intelligence**.
- If local mode eliminates prior anomalies and distributed mode reintroduces them -> bottleneck leans **distributed infrastructure instability**.

Guiding principle:
**SIMPLIFY -> STABILIZE -> VALIDATE -> DISTRIBUTE LATER**

---

## V26.4.7 Participation Restoration Validation Addendum

During local single-machine validation, also track whether decision logic now behaves as an opportunity-capture engine with controlled safety:

- Count `WAIT_VALID` cycles and confirm they do not grow without bound.
- Confirm `wait_valid_cycles > WAIT_TIMEOUT_CYCLES` produces `EXECUTE_CAUTIOUS` when directional authority is still valid and no hard safety block exists.
- Confirm `TRANSITION_WAIT` weakening counters do not persist beyond `TRANSITION_WAIT_MAX_CYCLES` without an auto-release or confidence degradation path.
- Confirm weak NOVA trend-momentum events preserve `bias`, `action`, `market_mode`, and `bb_state` while applying a confidence penalty.
- Continue treating stale state, malformed payloads, invalid SL/TP, catastrophic spread, duplicate order protection, and hard risk controls as authoritative hard stops.

Additional metrics to capture in `decision.json` snapshots:
- `wait_valid_cycles`
- `wait_timeout_cycles`
- `wait_recovery_lifecycle`
- `transition_wait_max_cycles`
- `transition_wait_released`
- `participation_release`
- `participation_release_reason`
- `confidence_penalty`
- `momentum_governance_state`

## V26.4.8 Intent-to-Payload Verification Checklist Addendum
During Local Single-Machine mode, verify these additional pass criteria:

1. For every `decision=TRADE` with `action=BUY` or `action=SELL`, confirm `sl > 0`, `tp > 0`, `management != NO_TRADE`, and `entry_slot > 0`.
2. Confirm `risk_payload_construction` is either `UNCHANGED_ALREADY_VALID` or `BUILT_BEFORE_VALIDATION` for executable trades.
3. If `risk_payload_construction=FAILED_NO_ENTRY_PRICE`, confirm the final decision is controlled `WAIT_VALID` and not an executable malformed trade.
4. Confirm weak NOVA momentum appears as `momentum_governance_state=SOFTENED_WEAK_MOMENTUM` with confidence penalty instead of an unconditional `NO_TRADE`.
5. Confirm strong `TRANSITION+NORMAL` setups with `score_gap >= 4` and only slight RSI miss produce cautious execution or explicit risk-construction wait, not generic `NO_TRADE`.
6. Confirm cooldown / fast participation logs no longer end in `FAST_PARTICIPATION_NOT_TRADE` when BUY/SELL intent is preserved and infrastructure is fresh.

## 11) V26.5 Execution Quality Validation Addendum

During each local validation run, record execution quality fields from every refreshed `decision.json`:
- `entry_location_score`
- `entry_location_grade`
- `entry_location_positive_factors`
- `entry_location_negative_factors`
- `active_execution_leg`
- `execution_legs`
- `scale_policy`
- `profit_lock_ladder`
- `wait_state`
- `wait_reason`

Pass criteria:
- Late/chasing locations publish `WAIT_ENTRY_LOCATION` or low-confidence `WAIT_VALID` instead of forcing poor participation.
- Valid pullback/continuation locations preserve BUY/SELL intent and produce an executable risk payload.
- Leg metadata remains one-directional and never enables martingale, loser averaging, or buy+sell hedge behavior.
- Profit-lock ladder metadata is present on decision payloads for executor-side profit extraction testing.

## 12) Daily Expectancy Review

After each validation day, run:
- `python analysis/analyze_trade_memory.py`

Review these metrics before changing participation frequency or size:
- Win Rate
- Average Win
- Average Loss
- Profit Factor
- Expectancy
- Runner Capture Rate

Decision gate:
- Future architecture changes must be justified by improved expectancy, not higher trade count.
