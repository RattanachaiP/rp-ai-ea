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

## PR187 governed advisory Execution Environment Intelligence rule

**Rule #022 — Advisory Execution Environment Intelligence.** PR187 may consume only
immutable, canonical PR186 Execution Readiness records, reports, or snapshots. It
verifies exact repository, snapshot, provenance, policy, engine, replay, and
historical-lineage partitions before producing immutable environment-quality
evidence. `ENVIRONMENT_READY_FOR_FEASIBILITY` means only that the environment
assessment completed for future PR188 feasibility review. It grants no strategy,
bias, direction, risk, publication, activation, broker, position-management, exit,
`OrderSend`, or execution authority.

## PR188 governed advisory Execution Feasibility rule

**Rule #023 — Advisory Execution Feasibility.** PR188 consumes only immutable,
canonical PR186 Execution Readiness records and PR187 Execution Environment
records. It verifies repository, snapshot, provenance, policy, engine, replay,
and historical-lineage continuity before producing immutable feasibility
evidence. `EXECUTION_FEASIBLE` means only that advisory prerequisites are
satisfied for future PR189 package assembly. It grants no strategy, bias,
direction, risk, publication, activation, broker, position-management, exit,
`OrderSend`, or execution authority.

## PR189 governed advisory Execution Package Assembly rule

**Rule #024 — Advisory Execution Package Assembly.** PR189 consumes only exact,
immutable canonical PR186 Execution Readiness, PR187 Execution Environment, and
PR188 Execution Feasibility records. It verifies their repository, snapshot,
provenance, policy, engine, replay, and cross-stage lineage partitions and only
assembles them into an immutable `ExecutionPackage`. `PACKAGE_READY` means solely
that a complete advisory package was assembled for downstream consumption. It
grants no strategy, bias, direction, risk, publication, activation, broker,
position-management, exit, `OrderSend`, or execution authority.

## PR190 governed advisory Execution Package Consumer Interface rule

**Rule #025 — Immutable Execution Package Consumption.** PR190 is the first
downstream consumer of PR189 and owns only fail-closed loading, canonical
deserialization, UUID, SHA-256, snapshot, version, and replay-identity checks,
and immutable package access. It produces no new artifact and never evaluates,
scores, infers, recommends, modifies, repairs, persists, publishes, activates,
or authorizes an `ExecutionPackage`. The withdrawn validation gateway is not an
architecture stage. Execution authority remains exclusively in the MT5 Executor.

## PR191 governed Execution Confidence Integration rule

**Rule #026 — Immutable Execution Confidence Context.** PR191 consumes only the
immutable `ExecutionPackage` returned by PR190 and projects its readiness,
environment, feasibility, replay, version, and package metadata into an
immutable, advisory-only `ExecutionConfidenceContext`. Invalid, missing,
incompatible, corrupted, or replay-mismatched packages fail closed without
repair. PR191 cannot alter confidence scoring, strategy, bias, risk, decisions,
publication, broker communication, orders, positions, exits, or execution.

## PR192 governed Execution Contract rule

**Rule #027 — Canonical Immutable Execution Context.** The V26 Runtime and MT5
Executor communicate only through the versioned, canonical, immutable PR192
`ExecutionContext`. The contract contains execution-facing metadata only and is
integrity-bound by canonical serialization and SHA-256. The Executor may not
read an `ExecutionPackage` or any other governance artifact. Missing, unknown,
non-canonical, corrupted, UUID-invalid, version-incompatible, engine-incompatible,
or replay-mismatched payloads fail closed without repair, fallback, or partial
loading. PR192 creates no trading intent and has no broker, order, position, or
exit authority.

## PR194 executor-side Execution Context consumption rule

**Rule #028 — Fail-closed Execution Context Consumption.** The MT5 Executor may
load only the immutable canonical PR192 `ExecutionContext` published as
`execution_context.json` by PR193. It verifies canonical UTF-8 JSON, the exact
field set, UUIDs, SHA-256, contract and engine versions, replay identity,
timestamp, and advisory marker. Failure permits no fallback, repair, or partial
acceptance. The consumer may not access Runtime internals, strategy objects,
`ExecutionPackage`, `ExecutionConfidenceContext`, or governance artifacts and
creates no trading intent or execution authority.

## PR195 governed Executor activation rule

**Rule #029 — ExecutionContext-gated Activation.** The existing MT5 Executor may
be activated only after the PR194 consumer returns a validated immutable PR192
`ExecutionContext` and the Runtime is explicitly ready. Invalid context,
consumer, contract, or Runtime state rejects activation permanently for that
activation lifecycle. There is no fallback or legacy activation trigger. PR195
owns activation only; broker safety, order submission, positions, stops,
targets, and exits remain unchanged and exclusively Executor-owned.

## PR196 production execution wiring rule

**Rule #030 — Sole Production Startup Path.** Production startup composes the existing PR193 publisher, PR194 consumer, and PR195 one-shot activator. The configured MT5 Common Files root must be verified before publication; the terminal may start only after the exact published `ExecutionContext` is consumed and the Runtime reports `READY`. Every failure fails closed without a legacy startup or alternate trigger. PR196 adds no strategy, confidence, broker, order, position, or exit behaviour.

## PR201 live outcome capture rule

**Rule #031 — Immutable Broker-confirmed Outcome Evidence.** PR201 passively captures one canonical `LiveOutcomeRecord` only after a broker-confirmed trade completion. Records are integrity-bound, append-only, duplicate-rejecting, and trace the Decision, ExecutionContext, publication (when applicable), activation, order, broker, position, exit, and final result identities. Capture has no strategy, scoring, learning, attribution, governance, broker, `OrderSend`, position-management, exit, or execution authority.

## PR203 completed-trade event rule

**Rule #032 — Canonical Completed Trade Event.** After broker-confirmed trade completion, the production host emits exactly one immutable, canonical `CompletedTradeEvent`. The passive production outcome integration accepts this event only; broker-specific objects terminate at the host boundary. Invalid identity, integrity, replay, chronology, or duplicate events fail closed. Event publication has no execution or decision authority.

## PR206 passive pattern discovery rule

**Rule #033 — Evidence-only Pattern Discovery.** PR206 consumes only immutable
PR205 `OutcomeAttribution` records and their exact PR203 `CompletedTradeEvent`
and PR201 `LiveOutcomeRecord` sources. It verifies integrity, lineage, replay,
sample sufficiency, and duplicate identity before emitting immutable,
deterministic, SHA-256-bound operational `Pattern` records. Patterns are
descriptive candidate knowledge only: they make no recommendation, perform no
optimisation, and grant no Runtime, Strategy, governance, broker, order,
position, exit, or execution authority.

## PR207 passive knowledge formation rule

**Rule #034 — Evidence-only Knowledge Formation.** PR207 consumes only an
immutable PR206 `Pattern` and its exact PR205 `OutcomeAttribution`, PR203
`CompletedTradeEvent`, and PR201 `LiveOutcomeRecord` evidence. It verifies the
complete integrity and replay lineage before applying declared deterministic
qualification thresholds and emitting an immutable `CandidateKnowledge` as
`CANDIDATE`, `QUALIFIED`, or `REJECTED`. Qualification performs no prediction,
recommendation, optimisation, or source modification and grants no Runtime,
Strategy, governance, broker, order, position, exit, or execution authority.
