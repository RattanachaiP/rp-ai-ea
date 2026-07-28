# ARCHITECTURE_RULES — V27 Runtime / V28 Decision-Rebuild Governance

## Sole authority
This document, `CURRENT_SYSTEM_STATE.md`, `DECISION_FLOW_MAP.md`, and `EMERGENCY_PATCH_POLICY.md` are the authoritative architecture documents for V27 changes.

## PR255 evidence-review backlog rule

PR255 is an offline, advisory-only consumer of explicitly selected authoritative
production evidence. It may emit only `production_improvement_backlog.json` and
may create items only from measured adverse observations supported by a governed
schema rule. Every item remains `PENDING_HUMAN_REVIEW`. Priority is triage order,
maps from severity only, and is not change approval. Items have snapshot-scoped
identity and evidence references an explicit digested source record. Missing-stage
evidence never assigns failure ownership. PR255 cannot modify, tune, invoke,
activate, or authorize AI, Strategy, Runtime, execution, position management,
learning, or production.

## PR254 production pipeline validation rule

PR254 is an offline, read-only consumer of an explicitly selected continuous
Demo pipeline trace snapshot. It may produce only
`pipeline_validation_report.json`. It cannot import, invoke, delay, retry,
modify, or authorize any trading subsystem. Missing stages and failures remain
explicit classified evidence. Raw lifecycle identifiers are input-only and the
report exposes report-local references. PR254 owns no threshold, pass/fail claim,
production approval, or promotion gate.

## PR253 governed trading-performance analytics rule

PR253 is an offline, read-only consumer of explicitly selected Runtime telemetry,
completed-trade exports, MT5 ReportHistory, Experts logs, and Journal logs. It may
produce only aggregated production and daily evidence reports. It cannot import,
invoke, delay, modify, score for, or otherwise influence AI Decision, Strategy,
Risk Construction, Writer, Runtime, Executor, Broker Safety, `OrderSend`, position
management, exits, learning, or promotion. Missing evidence remains explicitly
unavailable and must never be inferred or replaced with a behavioral recommendation.

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

## PR183 governed advisory Decision Context construction rule

## PR250 governed outcome-evidence acquisition rule

PR250 `learning.outcome_evidence` is the sole operator-controlled acquisition boundary for PR173 input. It admits only exact canonical replay-verifiable `PR250.OUTCOME_EVIDENCE.1.0` manifests, preserves complete normalized rows append-only under `learning_data/outcome_evidence`, and composes one exact evidence UUID into the existing PR173 engine/repository. Acquisition-owned row replay identity is SHA-256 over a documented domain and complete immutable normalized source-event payload; arbitrary digests fail. There is no latest selection, approval, attribution logic, learning policy, mining, Runtime, Strategy, Risk, Writer, Executor, broker, order, position, or exit authority. PR175 approval remains separate.

## PR248 governed bootstrap composition rule

The canonical learning lineage is PR173 outcome attribution, PR174 learning
policy, PR175 approved-evidence pattern mining, PR176 pattern memory, PR177
validation, PR178 promotion assessment, PR179 knowledge registry, PR180 runtime
knowledge packaging, PR181 eligibility, PR182 confidence, PR183 context, and
PR184 intelligence. PR173's operator-supplied immutable outcome evidence and
PR175's separately approved evidence envelope are the external genesis boundary;
neither may be synthesized from an empty clone. Bootstrap inspection, planning,
and verification are read-only. Construction accepts an exact operator-selected
upstream snapshot and delegates persistence to the downstream owner engine. It
must not select latest evidence, approve, activate, or grant trading authority.
The constructed result identity must come from the owner report and match exactly
one canonical snapshot; repository order cannot confer identity. PR180 consumes a
complete exact PR179 snapshot in one owner lifecycle, including multi-record state.
Read-only verification may validate the unique activation and production startup
configuration boundary but may not invoke Runtime or any trading subsystem.

PR183 Decision Context construction may occur only through the PR183 owner engine from
an exact canonical PR182 confidence artifact and its verified repository/snapshot
lineage. The operator construction command may compose exact snapshot lookup with that
engine and the PR183 append-only repository only. It may not select a latest artifact,
fabricate an identity, write repository JSON directly, construct or activate PR184, or
invoke Runtime, Strategy, or Executor behavior.

## PR184 governed advisory Decision Intelligence rule

**Rule #019 — Advisory Decision Intelligence.** PR184 may consume only immutable,
canonical PR183 Decision Context records, reports, or snapshots. It verifies exact
repository, snapshot, provenance, policy, and engine partitions before constructing
immutable Decision Intelligence. PR184 also owns an immutable production-input
activation record binding one exact intelligence/snapshot/repository/policy/engine
bundle. `DECISION_INTELLIGENCE_READY` means only that the
advisory artifact was constructed; it grants no strategy, bias, direction, risk,
publication, activation, broker, position-management, exit, or execution authority.
Only PR185 may consume PR184 Decision Intelligence.

The activation is committed only by the explicit PR184 owner command from exact
operator-selected intelligence and snapshot UUIDs. Its canonical schema, owner,
READY state, approval timestamp, lineage, and compatibility partitions are bound by
its deterministic UUID and digest. Construction, startup, and Runtime may not create,
infer, repair, replace, or select an activation from repository contents.

PR184 operator inspection is read-only, deterministic evidence. It enumerates every
canonical intelligence, snapshot, and exact pair without choosing a latest, newest,
READY, filename-ordered, or timestamp-ordered candidate. Its
`ELIGIBLE_FOR_OPERATOR_REVIEW` classification is neither approval nor activation and
grants no production, Runtime, trading, or execution authority. Only explicit human
review followed by the owner activation command with exact identities and an explicit
UTC approval timestamp can create the canonical activation.

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
`CANDIDATE`, `THRESHOLD_ELIGIBLE`, or `REJECTED`. Threshold eligibility records
only declared policy-threshold satisfaction and performs no prediction,
recommendation, optimisation, or source modification and grants no Runtime,
Strategy, governance, broker, order, position, exit, or execution authority.

## Production Execution Initialization rule

**Rule #035 — Exact governed startup initialization.** The canonical operator startup
starts from the exact PR184 Decision Intelligence bundle named by the sole immutable
owner-governed production-input activation record and
explicit, timestamped PR187 environment observations. It invokes PR185 through its
owning engine and repository, passes only the resulting exact Recommendation identity
to production initialization, invokes PR186, persists PR186 and the
canonical environment evidence through their owning repositories, invokes and persists
PR187 and PR188, and passes only the identities returned by those engines to the PR208
Runtime Bootstrap. PR208 remains the sole composition of PR189 package assembly, PR190
package consumption, environment handoff, and Runtime invocation. Activation resolution
must be unique and may not derive authority from current repository contents, timestamps,
file ordering, READY-state scanning, or a latest-record choice. No downstream UUID may
be supplied, fabricated, selected as latest, or recovered; any missing, non-ready,
incompatible, corrupt, or lineage-invalid stage prevents Runtime invocation.

## PR242 runtime clock skew policy rule

**Rule #036 — Immutable Environment Observation clock skew.** Environment
Observation compares the MT5 broker-clock `heartbeat_unix` with Python host wall
time under the immutable, finite, non-negative `max_clock_skew_seconds` policy
field. The field participates in the canonical policy payload, SHA-256 digest, and
deterministic UUID. Equality at the declared boundary is accepted; only a heartbeat
strictly beyond host time plus the declared tolerance is future-dated and rejected.
This policy changes no stale, identity, sequence, telemetry, integrity, or fail-closed
gate and grants no decision, strategy, risk, publication, Writer, package, Executor,
broker, `OrderSend`, or execution authority.
