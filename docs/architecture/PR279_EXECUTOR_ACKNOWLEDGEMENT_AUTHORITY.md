# PR279 Executor Acknowledgement Authority

## Executor-origin boundary

PR279 authenticates acknowledgement; it does not manufacture it. The existing V27 Production
Executor produces an immutable, signed `ExecutorAcceptanceAttestation` only after accepting the
exact PR278 `ExecutorAdmissionAuthorization`. The attestation binds both PR278 authorization
identities, executor identity/version/instance/session, runtime instance, activation generation,
artifact, runtime contract, target environment, executor policy, acknowledgement authority,
acceptance time, and a replay-safe nonce.

The governance bundle carries that executor-facing authorization, signed attestation, exact PR278
`AdmissionRegistryEntry`, current authoritative PR278 Admission Registry snapshot, and current
PR279 registry snapshot. Registry objects are governance proofs rather than operational inputs.
PR279 checks the exact entry and every authorization/evidence binding instead of accepting a
`RuntimeAdmissionAuthorization` directly.

## Mandatory authentication and lineage

The authority reconstructs the content-addressed attestation and authenticates its HMAC against a
trusted key selected by executor identity/version/instance. It verifies the configured boot/session,
bounded and non-future acceptance time, authorization validity, exact artifact/contract/environment
lineage, policy and authority identities, exact current registry membership, upstream PR278
revocation status, lifecycle consistency, and replay uniqueness for the executor authorization,
attestation identity, and nonce/session binding. All checks are mandatory and failures record
immutable rejection evidence.

Admission revocation remains owned by PR278. PR279 reads current PR278 revocations but cannot create
or alter them. A PR278 revocation before acknowledgement fails current-effectiveness validation.
Post-acknowledgement invalidation is not owned by PR279 and is explicitly deferred to Architecture
Review or an extension of an existing upstream authority; a recorded acknowledgement remains
historical evidence and never overrides a later upstream invalidation.

## Acknowledgement-only output and lifecycle

One valid executor attestation atomically produces one `ExecutorAcknowledgement`, one historical
acknowledgement evidence record, one append-only registry entry, and one
`ExecutorAcknowledgementAuthorization`. The lifecycle is:

`AUTHORIZED → ACKNOWLEDGED → RECORDED → ACKNOWLEDGEMENT_COMPLETE`

`executor_admission_acknowledged=True` means only that PR279 authenticated and recorded the V27
executor's signed acceptance. `operational_execution_ready` and every runtime, broker, order, trade,
strategy, training, and evaluation capability remain false. PR279 has no runtime callback, broker
interface, order instruction, strategy input, or model input.

## Governance Pipeline Version 1 freeze

PR279 completes Governance Pipeline Version 1. No new Governance Authority may be introduced
without Architecture Review. Future governance work extends an existing authority rather than
fragmenting the pipeline; Phase 2 is Operational Governance and observability.
