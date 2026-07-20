# RP AI Brain implementation mapping

**Audit scope.** This is a repository-only mapping performed on 2026-07-20. It
does not change runtime behaviour. The required `brain/` directory and all 11
requested Brain documents (including `brain/DATA_CONTRACT.md`) are absent from
the repository at this commit; consequently, this mapping uses the stage names
from the task as labels and does not claim conformance to an unavailable data
contract.

## Authoritative runtime and I/O findings

| Question | Repository evidence | Finding |
| --- | --- | --- |
| Authoritative Python decision engine | `CURRENT_SYSTEM_STATE.md`; `DECISION_FLOW_MAP.md`; `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` | The authoritative current engine is `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`. Its constants identify `codex-dev`, `V27`, and `trade-management-dashboard-architecture`. The V23/V24 engines are retained legacy files. `bridge/v28/` and `bridge/v29/` are separate proposal/validation code, not named as the current runtime. |
| Actual market-data input | `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` (`COMMON_SHARED_ROOT`, `BASE_PATH`, `FILE_PATH`, `read_market`) | The engine reads `C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\XAUUSD\market_state.json`, retrying fresh JSON reads and deriving freshness from file metadata and `heartbeat_unix`/`sequence_id`. The repository contains a sync consumer for this file, but no source writer for the live market-state payload. The producer is therefore external to the tracked tree. |
| Actual decision-publication path | `write_decision()` in the V26 engine; `mt5/v28/RP_AI_Executor_V28_CleanCore.mq5`; `mt5/RP_AI_TradeManagementDashboard_V27_1.mq5` | Python serializes a compatibility-normalized payload to `decision.tmp`, fsyncs it, then atomically replaces `...\XAUUSD\decision.json`. The V28 executor reads `RP_AI_EA\\shared\\XAUUSD\\decision.json`; the V27 dashboard reads `decision.json` as post-entry audit/management input. No tracked runtime launcher establishes which compiled MQL EA is attached in a terminal. |

### Current authoritative runtime path

`external/untracked market-state producer`
`-> Common Files .../XAUUSD/market_state.json`
`-> read_market()`
`-> build_decision()`
`-> in-engine legacy/quality/structure/timing layers`
`-> write_decision()` (normalization, risk construction, validation, atomic publication)
`-> Common Files .../XAUUSD/decision.json`
`-> attached MT5 executor reads the payload / V27 dashboard reads it for post-entry management and audit`
`-> MT5 Common Files trade statistics / trade_memory.csv`
`-> analysis Python utilities.`

## Existing-component-to-Brain mapping

| Brain stage | Existing paths and functions/classes | Current input -> output | Mapping assessment |
| --- | --- | --- | --- |
| Market Data | V26 `read_market()`, `annotate_market_state_time_sync()`, `is_market_state_stale_by_time_sync()`; `bridge_sync/sync_market_state_to_pc_FORCE_ALWAYS_ATOMIC_FIX.ps1` | External JSON -> raw dict augmented with file path, modification time, age, signature, heartbeat, and sequence fields. | Present as a file adapter and freshness guard. The canonical market-state producer/schema is not present. |
| Market Perception | V26 `get_scores()`, `classify_bb_state()`, `classify_bb_extreme()`, candle-series helpers, `get_candle_data()`, `candle_intelligence_layer()` | Raw bid, MA, BB, RSI, MACD, score, and optional candle arrays -> BB/candle/momentum/wick telemetry. | Present, but raw observations and derived interpretations coexist in one large module. |
| Market Understanding | V26 `classify_market()`, `classify_structure_trend()`, `detect_market_structure()`, `detect_bos_choch()`, `detect_liquidity_sweep()`, `detect_distribution_accumulation()`, `detect_momentum_decay()`, `market_structure_exhaustion_master_gate()` | Perception fields -> `market_mode`, BB state, structure/exhaustion/late-entry findings. | Partially present. `market_mode` is also directly driven by indicator scores in `classify_market()`, so score aggregation is acting as market understanding. |
| Market Reasoning | V26 `detect_directional_dominance()`, `get_selective_range_reversal_bias()`, `soft_direction_lock_v2()`, `entry_quality_gate()`, `nova_brain_filter()`, pullback/continuation and S/R entry-location functions, and `build_decision()` | Understanding/perception fields -> BUY/SELL thesis, entry type, initial SL/TP, reason, and wait/block state. | Present but distributed across many sequential veto/enrichment functions rather than an explicit evidence/thesis object. |
| Probability | V26 `compute_analysis_quality()`, `apply_v26_execution_confidence_engine()`, `compute_entry_location_score_v26_5()`, `compute_execution_timing_layer_v26_6_5()` | Scores and diagnostics -> `analysis_quality`, `execution_confidence`, `execution_state`, location and entry-window scores. | Heuristic confidence exists; no calibrated probability model, forecast distribution, calibration metric, or isolated probability contract exists. |
| Expected Value | V26 `planned_rr`/RR enforcement in risk construction and validation, `apply_expectancy_entry_filters_v26_6_2()`, `apply_session_loss_governor_v26_6_2()`; `analysis/trade_statistics.py` metrics; `analysis/trade_autopsy_engine.py` | Planned reward/risk and historical closed trades -> RR gates, loss/profit-protection metadata, and offline expectancy reports. | Partial. It is rule-based expectancy gating plus offline realized statistics, not a decision-time expected-value calculation with probability, payoff distribution, costs, and alternatives. |
| Position Intelligence | V26 `risk_points_for_mode()`, `construct_risk_payload_before_validation()`, `build_execution_legs_v26_5()`, `apply_early_participation_sizing_v26_6()`, exit-authority metadata functions; `bridge/trade_management_dashboard.py::load_trade_management_dashboard()`; V27 dashboard MQL | Directional trade + dashboard profile -> SL/TP/risk fields, execution legs, sizing, management/exit metadata. | Present but split across Python initial-payload construction and MQL post-entry management, with dashboard configuration imported by Python. |
| Decision Publication | V26 `ensure_ea_v17_compat_fields()`, `validate_final_decision_payload()`, `enforce_final_execution_state_v28()`, `attach_final_write_metadata()`, `write_decision()` | Internal decision dict -> legacy-compatible, validated, atomically published `decision.json`. | Present and authoritative. This is a high-coupling compatibility boundary, not an explicit versioned Brain adapter. |
| Learning | V26 `load_learning_state()`, `save_learning_state()`, `read_trade_result_records()`, `update_learning_from_trade_results()`, `make_learning_key()`; `analysis/trade_statistics.py::CompletedTrade` and metrics; `analysis/trade_autopsy_engine.py` | `learning_state.json`/trade-result records and MT5 CSV -> adaptive gap adjustment and offline metrics/autopsies. | Present in two forms: a live in-engine adjustment and offline analysis. There is no demonstrated closed-loop ownership, lineage, or promotion gate. |

## Current flow and responsibility boundaries

1. `build_decision()` reads raw indicator fields and source-provided `buy_score`/
   `sell_score`, classifies BB and market mode, chooses a directional action, and
   invokes quality, NOVA, candle, exhaustion, structure, pullback, timing, and
   entry-location functions.
2. `write_decision()` performs another extensive sequence: compatibility
   normalization; quality, confidence, timing, sizing, risk, protection and
   final-state processing; dashboard loading; risk-payload construction;
   payload validation; and atomic write. This means decision intelligence is
   not complete at the end of `build_decision()`.
3. `mt5/v28/RP_AI_Executor_V28_CleanCore.mq5` is an execution reader that
   validates and sends a trade. The architecture documents restrict its
   terminal authority to payload/schema/freshness/broker safety classes.
4. `mt5/RP_AI_TradeManagementDashboard_V27_1.mq5` is explicitly post-entry
   dashboard/exit management. It reads both JSON files and emits trade
   statistics; it is not a repository evidence source for the market-state
   writer.

## Contract status and field-name observations

No `brain/DATA_CONTRACT.md` exists, so a definitive compatibility comparison is
blocked and must not be fabricated. The existing payload has multiple aliases
that a future contract must explicitly resolve rather than silently remove:

| Semantic value | Existing names observed |
| --- | --- |
| Decision/action | `decision`, `action`, `bias`, `direction`, `intended_action`, `ai_intended_action` |
| Market regime | `market_mode`, `mode`, `ai_intended_mode` |
| BB state | `bb_state`, `bb`, `confirmed_bb_state`, `ai_intended_bb_state` |
| Price / protection | `entry_price`, `price`, `bid`; `sl`, `stop_loss`, `take_profit`, `tp`, `tp1` |
| Position sizing | `risk_fraction`, `position_size_multiplier`, `position_size_factor`, `ai_intended_position_size_factor` |
| Management | `management`, `mgmt`, `management_mode`, `effective_management_mode`, `ai_intended_management` |
| Freshness identity | `sequence_id`, `market_state_sequence_id`, `heartbeat_unix`, `market_state_age_sec`, `decision_age_sec` |

These aliases are compatibility debt and a migration risk. They are not labeled
as contract violations until the missing Brain data contract is supplied.
