# RP TRADING GPT — VERSION CHANGELOG

==================================================
PR169 GOVERNED KNOWLEDGE ROLLBACK ORCHESTRATION ENGINE
==================================================

Status: ACTIVE

* Added `learning.rollback_orchestration` as the sole rollback planning and authorization boundary.
* Rollback evidence is deterministic, replay-safe, canonical JSON, atomic, and append-only under `learning_data/rollback_orchestration`.
* The component only validates and authorizes; it never mutates Runtime, the Active Knowledge Registry, or immutable KnowledgeVersions.

==================================================
V24.0 DEVELOPMENT PHASE
=======================

Current Status:
REAL MARKET OBSERVATION + AI ARCHITECTURE REBUILD

Major Direction Changes:

* shifted from indicator-based logic
* moving toward market behavior intelligence
* focus on expectancy improvement
* focus on pullback continuation
* focus on candle intelligence
* focus on runner behavior

==================================================
LATEST ACTIVE COMPONENTS
========================

Python AI:
ai_decision_engine_xauusd_v23_3_fresh_market_state_read_fix.py

Executor EA:
RP_AI_Executor_V19_1_HIGH_QUALITY_OVERRIDE_READY.mq5

Writer EA:
RP_Market_State_Writer_V13_FULL_LOGIC_ATOMIC_WRITE.mq5

Telegram:
RP_Telegram_AI_EA_Monitor_V1_1_UTF8_FIX.mq5

==================================================
LATEST MAJOR UPGRADES
=====================

* high quality override
* anti-flip filter
* trend continuation improvements
* analysis quality scoring
* dynamic score gap
* entry_allowed gate
* atomic write/retry fix
* file share lock reduction
* runner preservation improvements

==================================================
NEXT PRIORITIES
===============

1. Pullback Continuation Engine
2. Candle Intelligence Layer
3. Volume Intelligence
4. Exhaustion Detection
5. RR-First Gate
6. Dynamic Conviction Lot Sizing

==================================================
V26.6.2 / V26.6.2A PROFIT / LOSS ASYMMETRY + NO-PAUSE ADAPTIVE EXPECTANCY FIX
==================================================

Active runtime:
bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py

Purpose:
* repair negative expectancy caused by small wins and larger losses
* compress per-trade realized loss for 0.01 lot XAUUSD to the -$1.20 cap
* publish executor profit-lock instructions at +$0.80 and +$1.20
* disable weak gap trades and marginal TRANSITION+NORMAL participation
* V26.6.2A disables mandatory consecutive-loss pause and daily kill switch; loss clusters now diagnose, revalidate thesis, reduce size, and continue cautiously
* daily drawdown now activates DRAWDOWN_CAUTION_MODE instead of full stop unless catastrophic hard-risk state is reached
* add LOSS_REASON_CLASSIFIER telemetry for LATE_ENTRY, EXHAUSTION_ENTRY, CHOP_ENTRY, REVERSAL_ENTRY, SL_TOO_WIDE, BE_TOO_TIGHT, TREND_THESIS_FAILED, and EXECUTOR_MANAGEMENT_FAILURE

Non-goals:
* no new indicators
* no new strategy layers
* no new indicator stack
* no hard-safety bypass

## PR173 — Knowledge Outcome Attribution Engine

Added `learning.outcome_attribution` as an offline deterministic, advisory-only descriptive analytics domain. It aggregates immutable outcome evidence into non-causal observed associations and conditional outcome profiles; it does not duplicate `learning.analytics`, which remains authoritative for lineage, conflict, stability, and governance analytics.

## PR174 — Governed Learning Policy Gate
`learning.learning_policy` is an offline, immutable advisory structural and minimum-sample gate between PR173 attribution and a future pattern-mining stage. It does not assess profitability, statistical stability, historical repeatability, or promotion eligibility, and cannot mutate runtime or registry state.
