# RP TRADING GPT — VERSION CHANGELOG

==================================================
PR182 GOVERNED ADVISORY CONFIDENCE EVALUATION
==================================================

Status: IMPLEMENTED — PENDING ACCEPTANCE

- Reworked confidence evaluation from eligibility-state translation into nine explicit immutable evidence dimensions with policy-bound weights, normalization, half-even rounding, reason ordering, and advisory confidence bands.
- Added complete PR181 and upstream provenance retention, exact record/report/snapshot source binding, historical snapshot resolution, complete repository partitions, separated new/duplicate counters, replay collision protection, and source-context-bound confidence snapshot history.
- `CONFIDENCE_EVALUATED` records calculation completion only. PR182 never activates, applies, ranks, or weights knowledge for trading and never controls strategy, bias, direction, risk, decision publication, broker operations, position management, or execution.

==================================================
PR181 GOVERNED ADVISORY KNOWLEDGE ELIGIBILITY SELECTOR
==================================================

Status: ACTIVE

- Added `evaluate_eligibility()` as the canonical PR181 API for advisory eligibility recording; `select()` and `run()` remain compatibility aliases only.
- Bound every immutable eligibility artifact to the complete PR180, Registry, and Promotion governance partition; full lineage UUID/digest pairs; source states/reasons; immutable PR181 policy UUID/digest/version; and exact canonical PR180 snapshot/repository identity.
- Added deterministic historical package membership resolution, multi-reason eligibility classification, eligibility-specific states, complete source-bound reports and counters, and atomic append-only partitioned history with chained snapshots.
- `ELIGIBLE_FOR_CONFIDENCE_EVALUATION` authorizes only future PR182 confidence evaluation. PR181 has no activation, application, ranking, weighting, confidence, inference, Runtime decision, broker, position, exit, or execution authority.

==================================================
PR175 OFFLINE PATTERN MINING ENGINE
==================================================

Status: ACTIVE

* Added `learning.pattern_mining` as the deterministic offline pattern discovery boundary after PR174.
* Mining requires a content-addressed, versioned `ApprovedPatternMiningEvidenceEnvelope` whose deterministic UUID/digest binds canonically ordered unique samples, sample count, policy, attribution, replay, and outcome provenance. Duplicate identities, absent evidence, tampering, and mixed lineage fail closed.
* Strict feature/context allowlists, normalization rules, and the mining-config digest are part of replay identity. Candidates retain complete source provenance and reports bind the exact envelope and configuration.
* Outputs are immutable advisory-only `CandidatePattern` artifacts and atomic append-only reports. PR175 never creates, modifies, infers, promotes, activates, or publishes Runtime evidence and has no Registry, broker, or execution authority.

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

## PR176 — Pattern Memory Engine

Added `learning.pattern_memory` as the governed offline historical-memory stage after PR175. It retains complete PR175 provenance in independently content-addressed records, validates UUID and full-record digest at the model/replay boundary, persists records append-only, exposes immutable historical indexes, and records chained repository snapshots. The `STORED` state denotes persistence only, never approval or runtime activation. PR176 has no learning, promotion, activation, Registry, Runtime, decision-publication, broker, `OrderSend`, position-management, or execution authority.

## PR177 — Governed Pattern Validation Engine

Added `learning.pattern_validation` after PR176 Pattern Memory as an offline, immutable, fail-closed verification stage. PR177 reconstructs source memory records, retains complete PR176 provenance, binds reports to the exact source artifact and snapshot, and applies a versioned canonical historical-quality policy whose digest participates in domain-separated record and report identities. Replay distinguishes new history from duplicates, while atomic append-only persistence is protected by a chained validation snapshot history.

The neutral state `STATISTICALLY_CONSISTENT` is not pattern approval and never authorizes runtime use. PR177 owns historical validation, validation identity, replay verification, validation history, and repository reporting only. It does not own learning, approval, promotion, activation, Runtime or Registry mutation, decision publication, broker safety, `OrderSend`, position management, or execution.

## PR178 — Governed Promotion Policy Assessment Engine

- Added the offline, deterministic, immutable, advisory-only `learning.pattern_promotion` assessment boundary after PR177 and before a future separately governed Registry Admission stage.
- Added exact source-artifact and snapshot binding, complete PR176/PR177 provenance retention, recursive statistics validation, anti-downgrade enforcement, explicit engine/policy identities, replay counts, append-only history, and policy-bound snapshot chains.
- Canonical states are `REJECTED`, `INSUFFICIENT_PROMOTION_EVIDENCE`, and `POLICY_CRITERIA_MET`. The latter records criteria satisfaction only; it grants no publication, registration, activation, Runtime, trading, broker, position-management, exit, or execution authority.

## PR179 — Governed Advisory Knowledge Registry Admission Engine

Added `learning.knowledge_registry` after PR178 as an offline, immutable, append-only governance-recording stage. PR179 independently identifies its admission policy and engine, retains complete PR178 provenance, verifies replay and repository partitions, and creates deterministic advisory records and chained snapshots.

`ADVISORY_ENTRY_RECORDED` means only that an offline governance record exists. It grants no Runtime consumption, inference, activation, trading, publication, broker, position-management, exit, or execution authority.

## PR180 — Governed Advisory Runtime Knowledge Packaging Gate

Added `learning.runtime_knowledge` after PR179 as a fail-closed verification and advisory packaging boundary. PR180 identifies its immutable packaging policy, reconstructs exact PR179 report or record sources, binds every record to a canonical registry snapshot, retains complete PR179 provenance, and writes deterministic packages and chained repository snapshots append-only.

`ADVISORY_PACKAGE_PREPARED` means only that a canonical immutable package was prepared for a future separately governed selector. PR180 grants no Runtime decision use, selection, ranking, weighting, activation, inference, confidence, bias, scoring, direction, risk, decision-publication, broker, `OrderSend`, position-management, exit, or execution authority.
