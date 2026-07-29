# PR278 Runtime Admission Authority

## Governance boundary

PR278 authenticates and authorizes exactly one runtime admission. Its sole operational input
is the immutable PR277 `ExecutorHandoff`. A `RuntimeAdmissionGovernanceBundle` supplies the
current PR276 Release Registry and exact entry, current PR277 Activation Registry and exact
entry, an immutable Executor Admission Policy, the current Admission Registry snapshot,
expected identities for all three registries, and the admission timestamp. The registries
and entries are read-only governance proofs, not alternate execution inputs.

At admission time the authority reconstructs the handoff and registries, verifies exact
membership and full release, artifact, contract, environment, runtime, executor, generation,
evidence, event, and lifecycle lineage, and re-evaluates current effectiveness. Certificate
revocation, activation revocation, emergency rollback, release supersession, or local PR277
activation revocation denies admission. Expected-identity checks make stale release,
activation, and admission snapshots fail without mutation.

Executor identity and version are supplied by the content-addressed Executor Admission Policy;
neither is hard-coded into PR278. The policy also bounds maximum handoff age and the lifetime
of the resulting admission authorization. Replay uniqueness is enforced for the handoff and
for `(runtime_instance_identity, activation_generation)`, allowing a separately governed new
generation without allowing same-generation replay.

## Authorization, evidence, and lifecycle

A successful decision atomically records one expanded, content-addressed Runtime Admission
Evidence record, one bounded `RuntimeAdmissionAuthorization`, one data-only
`ExecutorAdmissionAuthorization`, and one append-only Admission Registry entry. The evidence
directly names the current registry entries, authorization, certificate, manifest, artifact,
runtime contract, environment, runtime instance, executor identity/version, activation
generation, and policy.

The only lifecycle is:

`REQUESTED → VALIDATED → ADMISSION_AUTHORIZED → RECORDED`

PR278 receives no executor acknowledgement and records none. `runtime_admission_authorized`
and `executor_admission_authorized` mean only that admission is authorized; they do not claim
that a runtime was launched or that the executor accepted or exercised authority.

PR278 never launches or modifies Runtime, invokes the Executor, connects to a broker, submits
an order, executes a trade, generates production strategy, trains a model, or evaluates a
model. No callback, broker interface, order instruction, strategy input, model input, or
mutable runtime object exists at this boundary.
