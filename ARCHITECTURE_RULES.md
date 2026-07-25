# ARCHITECTURE_RULES — V27 Runtime / V28 Decision-Rebuild Governance

## Sole authority
This document, `CURRENT_SYSTEM_STATE.md`, `DECISION_FLOW_MAP.md`, and `EMERGENCY_PATCH_POLICY.md` are the authoritative architecture documents for V27 changes.

## V28 thinking-model rebuild gate

V28 is a proposal-stage replacement of the AI Decision Engine's thinking model,
not a V27 optimization. Its authoritative philosophy is documented in
`docs/v28/V28_DECISION_PHILOSOPHY.md` and its mandatory extension,
`docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`. No V28
implementation may begin until both documents are explicitly approved.

Until approval, V27 retains its runtime authority and the V27 no-touch AI
boundary below remains in force. Do not add V27 filters, cooldowns, waiting
logic, score adjustments, patches, or runtime layers in the name of V28.

## Mandatory subsystem separation
The runtime is separated into two independent subsystems:

1. **Subsystem A — AI Decision Engine**
   - Owns direction, bias, entry timing, market mode, position classification, and initial risk payload publication.
   - Must not own post-entry exit tuning.
   - Must not require recompilation or code edits for exit behavior tuning.

2. **Subsystem B — Trade Management Dashboard**
   - Owns post-entry open-position management.
   - Owns exit configuration, profile selection, runtime dashboard parameters, and import/export profile files.
   - Must route every effective exit decision through the Exit Authority Manager.

## V27 no-touch AI boundary
V27 trade-management optimization must not modify:
- AI direction logic
- Bias engine
- Entry engine
- Signal generation
- Market classification

## Exit authority rule
Only one effective exit owner is allowed at a time. Priority is:
`EMERGENCY_EXIT -> HARD_LOSS_CAP -> PROFIT_LOCK -> BREAKEVEN -> TRAILING -> RUNNER -> TIME_EXIT`.

## Runtime configuration rule
Dashboard parameters must be loaded at runtime from JSON profile files, with backward-compatible defaults if files are missing or malformed.

## RAIP V6 Governance rules

**Rule #014 — Governance verification.** No RAIP Intelligence Layer (Evidence, Knowledge,
Insight, or Recommendation) is Healthy unless Architecture Boundary, Schema Integrity,
Repository Integrity, Data Lineage, and Performance Health checks pass.

**Rule #015 — Independent observation.** Governance may observe RAIP Intelligence Layers but
must never modify them. It is an independent auditor and must not import, inspect beyond boundary
verification, invoke, delay, or influence the Decision Engine, Writer, Executor, Broker Safety, or
Risk Engine.

## RAIP V7 Executive Domain rule

**Rule #018 — Executive decision preparation.** Every Executive Decision Package must be deterministic, explainable, fully traceable, and governance-approved before presentation. The Executive Domain is advisory-only and may not modify the Trading or Intelligence domains, runtime payloads, deployment, or learning behavior.

## PR184 governed advisory Decision Intelligence rule

**Rule #019 — Advisory Decision Intelligence.** PR184 may consume only immutable,
canonical PR183 Decision Context records, reports, or snapshots. It verifies exact
repository, snapshot, provenance, policy, and engine partitions before constructing
immutable Decision Intelligence. `DECISION_INTELLIGENCE_READY` means only that the
advisory artifact was constructed; it grants no strategy, bias, direction, risk,
publication, activation, broker, position-management, exit, or execution authority.
Only PR185 may consume PR184 Decision Intelligence.

## PR185 governed advisory Decision Recommendation rule

**Rule #020 — Advisory Decision Recommendation.** PR185 may consume only immutable,
canonical PR184 Decision Intelligence records, reports, or snapshots. It verifies exact
repository, snapshot, provenance, policy, and engine partitions before constructing an
immutable Recommendation. Recommendation states and classifications are advisory evidence
only: they are not trading decisions and grant no strategy, bias, direction, risk,
publication, activation, broker, position-management, exit, or execution authority.

PR185 state/classification pairs are unambiguous: `RECOMMENDATION_READY` pairs only
with `READY_FOR_DECISION`, `RECOMMENDATION_MANUAL_REVIEW` pairs only with
`MANUAL_REVIEW`, and `RECOMMENDATION_NOT_READY` pairs only with `NOT_READY`.
No PR185 state or classification means BUY, SELL, HOLD, publication authorization,
or execution authorization.

## PR186 governed advisory Execution Readiness rule

**Rule #021 — Advisory Execution Readiness.** PR186 may consume only immutable,
canonical PR185 Recommendation records, reports, or snapshots. It verifies exact
repository, snapshot, provenance, policy, engine, replay, and historical-lineage
partitions before producing immutable Execution Readiness evidence.
`EXECUTION_READY_FOR_ENVIRONMENT_CHECK` means only that the advisory governance
pipeline is internally complete and consistent for future PR187 environment
assessment. It grants no strategy, bias, direction, risk, decision-publication,
runtime-activation, broker, position-management, exit, `OrderSend`, or execution
authority.
