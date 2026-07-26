# GOVERNANCE ARCHITECTURE SPEC

## Advisory governance pipeline

The governed advisory lineage is:

`Pattern Memory -> Runtime Confidence -> Decision Context -> Decision Intelligence -> Decision Recommendation -> Execution Readiness -> Execution Environment Intelligence -> future Execution Feasibility`.

Each stage consumes only the immutable canonical record, report, or snapshot types owned by its immediate predecessor. Each stage must verify source provenance, repository and snapshot membership, policy and engine partitions, replay identity, and historical lineage. Validation fails closed.

## PR186 — Governed Advisory Execution Readiness Engine

PR186 owns only execution-readiness evaluation, identity, provenance, policy, repository, snapshot, and report artifacts. It accepts PR185 Recommendation records, reports, and snapshots and emits immutable advisory-only `ExecutionReadinessRecord`, `ExecutionReadinessReport`, and chained snapshots.

The only readiness states are `REJECTED`, `INSUFFICIENT_EXECUTION_READINESS`, and `EXECUTION_READY_FOR_ENVIRONMENT_CHECK`. The ready state means solely that the advisory governance package is internally complete and consistent enough to be inspected by future PR187. It never means BUY, SELL, trade approval, execution approval, runtime activation, or permission to call `OrderSend`.

PR186 has no authority over market analysis, strategy, bias, direction, risk construction, decision publication, execution environment measurements, spread, latency, slippage, broker communication, runtime activation, position management, exits, or execution. Execution authority remains exclusively inside the MT5 Executor.

## Repository contract

PR186 artifacts reside below `learning_data/execution_readiness/`. Records and snapshots use canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests, atomic append-only writes, collision rejection, exact replay, and a digest-linked snapshot chain. Any provenance, snapshot, repository, policy, engine-version, or replay mismatch fails closed.

## PR187 — Governed Advisory Execution Environment Intelligence Engine

PR187 owns only environment-quality evaluation, identity, provenance, policy,
repository, snapshots, and reports. It accepts PR186 `ExecutionReadinessRecord`,
`ExecutionReadinessReport`, and `ExecutionReadinessSnapshot` artifacts and emits
immutable advisory-only environment evidence. Its states are `REJECTED`,
`INSUFFICIENT_ENVIRONMENT_INFORMATION`, and `ENVIRONMENT_READY_FOR_FEASIBILITY`.
The ready state permits only future PR188 feasibility assessment and grants no
trading or execution authority.

PR187 evaluates only canonical immutable observations bound to the exact PR186
artifact and policy partition. It never infers feed, stream, session, spread,
latency, slippage, liquidity, consistency, freshness, or completeness from a
readiness state. Missing and partial evidence fail closed as
`INSUFFICIENT_ENVIRONMENT_INFORMATION`; the configured policy thresholds and
minimum quality are retained in each result's declared policy artifact.

PR187 artifacts reside below `learning_data/execution_environment/` and use
canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests, atomic
append-only writes, collision rejection, exact replay, and a digest-linked snapshot
chain. All provenance, snapshot, repository, policy, engine-version, and replay
mismatches fail closed.

## PR188 — Governed Advisory Execution Feasibility Engine

PR188 owns only feasibility evaluation, identity, provenance, policy, repository,
snapshots, and reports. It accepts an exact canonical PR186
`ExecutionReadinessRecord` and its lineage-matched canonical PR187
`ExecutionEnvironmentRecord`. All other inputs fail closed. Its states are
`REJECTED`, `INSUFFICIENT_EXECUTION_FEASIBILITY`, and `EXECUTION_FEASIBLE`.
The feasible state means solely that advisory prerequisites are complete for
future PR189 package assembly and grants no trading or execution authority.

PR188 artifacts reside below `learning_data/execution_feasibility/` and use
canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests,
atomic append-only writes, collision rejection, exact replay, and a
digest-linked snapshot chain. Provenance, lineage, repository, snapshot,
policy, engine-version, and replay mismatches fail closed.

## PR189 — Governed Advisory Execution Package Assembly Engine

PR189 owns package assembly, identity, provenance, repository, snapshots,
reports, and integrity verification only. It accepts exact canonical PR186
`ExecutionReadinessRecord`, PR187 `ExecutionEnvironmentRecord`, and PR188
`ExecutionFeasibilityRecord` artifacts. It performs no evaluation, scoring,
inference, upstream override, or authorization. Its states are `REJECTED`,
`PACKAGE_INCOMPLETE`, and `PACKAGE_READY`; the ready state means solely that an
immutable advisory package is complete for downstream consumption.

PR189 artifacts reside below `learning_data/execution_package/` and use
canonical JSON, deterministic domain-separated UUIDs and SHA-256 digests,
atomic append-only writes, collision rejection, exact replay, and a
digest-linked snapshot chain. Provenance, lineage, repository, snapshot,
policy, engine-version, and replay mismatches fail closed. PR189 has no trading,
runtime, broker, `OrderSend`, position-management, exit, or execution authority.

## PR190 — Governed Advisory Execution Package Consumer Interface

PR190 is the first downstream consumer of the immutable PR189 package and owns
only fail-closed package loading, canonical deserialization, UUID and SHA-256
verification, snapshot membership, supported package and engine version checks,
replay identity, and immutable in-memory access. The proposed Execution Package
Validation Gateway is withdrawn because PR186 through PR189 already own their
respective validation responsibilities.

PR190 creates and persists no repository artifact, performs no evaluation,
scoring, inference, recommendation, readiness, environment, or feasibility
calculation, and never modifies or repairs a package. Failure has no recovery or
implicit repair. PR190 has no trading, runtime, broker, `OrderSend`,
position-management, exit, or execution authority; execution authority remains
exclusively inside the MT5 Executor.

## PR191 — Governed Execution Confidence Integration

PR191 accepts only the immutable in-memory `ExecutionPackage` delivered by the
PR190 consumer and produces one immutable, advisory-only
`ExecutionConfidenceContext` for V26. The context is a read-only projection of
package-bound readiness, environment, feasibility, version, metadata, and replay
identity. It performs no repository access, governance calculation, recovery,
repair, persistence, scoring, decision publication, or execution. A consumer
failure or invalid, missing, incompatible, corrupted, or replay-mismatched
package is rejected fail closed.

## PR192 — Governed Execution Contract

PR192 defines the sole public interface between the V26 Runtime and MT5
Executor: one immutable `ExecutionContext` containing execution UUID, decision
UUID, package UUID, replay UUID, execution confidence, readiness, environment,
feasibility, policy and engine versions, advisory marker, timestamp, contract
version, and integrity digest. It contains no strategy or governance object.

The canonical UTF-8 JSON codec requires the exact schema and verifies canonical
encoding, UUIDs, SHA-256 integrity, contract compatibility, engine compatibility,
and replay identity. Every mismatch fails closed without partial loading,
fallback, or repair. The Executor consumes this contract only and may not access
the PR186–PR191 governance artifacts. PR192 does not calculate confidence,
publish decisions, communicate with a broker, execute trades, manage positions,
or control exits.

## PR193 / PR194 — Publication and Executor Consumption

PR193 atomically publishes the complete canonical PR192 contract as
`execution_context.json`. PR194 is its MT5 Executor-side consumer and reads no
other artifact. It validates the exact schema, canonical UTF-8 JSON, UUIDs,
digest, replay identity, contract and engine compatibility, timestamp, and
advisory marker before returning the immutable in-memory context. Missing or
invalid input is rejected in full without fallback, repair, or partial access.
This boundary adds no strategy, decision, confidence, broker, order, position,
stop, target, or exit behavior.

## PR195 — Governed Executor Activation

PR195 replaces the legacy activation trigger with the immutable
`ExecutionContext` accepted by PR194. A one-shot activation requires successful
consumer and contract verification and an explicit ready Runtime state. Every
failure rejects activation without fallback or partial acceptance.

The activation callback starts the existing MT5 Executor without supplying new
execution behavior. PR195 does not own broker safety, `OrderSend`, positions,
stop loss, take profit, exit authority, strategy, confidence, or risk; all
Executor execution responsibilities remain unchanged.

## PR196 — Production Execution Wiring

PR196 composes the existing PR193, PR194, and PR195 boundaries. The Runtime publishes `execution_context.json` into the configured MT5 Common Files path; PR194 consumes that exact file and PR195 invokes the existing production host's MT5 Executor startup callback only while Runtime is explicitly `READY`.

The production lifecycle is one-shot and fail-closed, has no legacy startup, and introduces no new layer. It does not calculate confidence or own strategy, broker safety, `OrderSend`, positions, stops, targets, or exits.

## PR201 — Live Outcome Capture

PR201 is an operational evidence boundary, not a governance or execution stage. It accepts only a complete broker-confirmed closed-trade fact set and the exact immutable PR192 `ExecutionContext`. It verifies UUID lineage, required tickets, broker completion, canonical UTC chronology, replay identity, and all required execution and result values before producing a deterministic immutable `LiveOutcomeRecord`.

Records reside below the configured `operational_evidence/live_outcomes/` root as canonical JSON and use deterministic UUIDs, SHA-256 integrity, atomic append-only creation, and strict duplicate rejection. Optional publication identity/timestamp and optional broker-provided MFE/MAE are represented explicitly as unavailable, never inferred. PR201 performs no analytics, scoring, learning, attribution, recommendation, governance decision, broker communication, `OrderSend`, position management, exit control, or execution.

## PR203 — Completed Trade Event Standardization

The production host converts final broker-confirmed completion facts into one immutable `CompletedTradeEvent`. It has canonical UTF-8 JSON, deterministic ordering, strict UTC chronology, deterministic identity, SHA-256 integrity, replay identity, and duplicate rejection. Passive outcome integration and live outcome capture consume only this event, never broker-specific objects. This changes no execution authority, broker safety, Runtime, Strategy, Governance, ExecutionContext, `OrderSend`, analytics, attribution, or learning.

## PR206 — Pattern Discovery

PR206 is outside the advisory governance and execution pipelines. It consumes
only exact immutable PR205 attribution and PR203/PR201 parent evidence and
produces descriptive candidate operational knowledge. Its repository is
canonical, atomic, append-only, deterministic, SHA-256 integrity-bound,
duplicate-rejecting, and replay-safe. Insufficient samples and any source or
replay inconsistency fail closed. It cannot recommend, optimise, modify source
evidence, or influence Runtime, Strategy, governance, broker, order, position,
exit, or execution behaviour.

## PR207 — Passive Knowledge Formation

PR207 remains outside the advisory governance and execution pipelines. It
consumes only one immutable PR206 `Pattern` and the exact immutable PR205,
PR203, and PR201 evidence from which that pattern was discovered. Complete
source reconstruction, integrity, replay lineage, and duplicate checks precede
deterministic evidence qualification; every validation failure fails closed.

PR207 emits immutable `CandidateKnowledge` classified as `CANDIDATE`,
`QUALIFIED`, or `REJECTED` using only declared thresholds. Its canonical,
atomic, append-only repository uses deterministic identities, SHA-256 integrity,
fsync protection, collision rejection, and exact replay. It is the only
producer of knowledge candidates for future adaptive systems, but cannot
predict, recommend, optimise, modify operational evidence, or influence
Runtime, Strategy, governance, broker, order, position, exit, or execution
behaviour.
