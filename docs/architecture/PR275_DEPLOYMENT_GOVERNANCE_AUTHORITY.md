# PR275 Deployment Governance Authority

## Purpose and authority boundary

PR275 establishes the immutable governance boundary between an eligible promotion and a
future production-release authority. It validates and certifies release governance eligibility; it does
not deploy or activate an artifact, alter Runtime or Strategy, access a broker, execute a
trade, or perform production release. A `ReleaseRequest` is an auditable request to the
separate release authority—not permission or executable release machinery.

The authority consumes one `DeploymentGovernanceBundle`. The bundle reconstructs and binds
the exact Promotion Result and Promotion Registry, Governance Queue Entry and Governance
Queue Registry, Human Approval Record and append-only Human Approval Registry, deployment
artifact, target environment, runtime contract, assessment time, and Deployment Policy. It
does not reconstruct training, evaluation, or qualification decisions.

## Eight deployment gates

1. Promotion eligibility
2. Human approval validation
3. Deployment policy validation
4. Evidence completeness
5. Registry lineage validation
6. Artifact integrity
7. Release routing integrity
8. Manifest binding integrity

All eight gates must pass. Policy mismatch, missing, expired, replayed, superseded, or revoked
approval, governance-queue absence, broken registry lineage, incomplete promotion evidence,
artifact/build incompatibility, environment/runtime mismatch, or release-routing mismatch
produces `DEPLOYMENT REJECTED`. Rejected results produce neither a manifest nor a release
request. Timestamps use the canonical whole-second UTC `YYYY-MM-DDTHH:MM:SSZ` form. Policy
bounds approval age and each approval carries an exclusive expiry.

## Artifact and routing evidence

`DeploymentArtifact` has a content-addressed identity distinct from candidate identity. It
binds the candidate, package content hash, model hash, build provenance, compatibility
evidence, target environment, and runtime contract. `TEST`, `DEMO`, and `LIVE_PRODUCTION`
are distinct environment classes and policy explicitly permits classes and runtime contracts.

Human approval binds the exact Promotion Approval Request, Promotion Policy, governance
policy, review route, approval authority, reviewer role, and candidate. The authoritative
queue registry must contain the exact request's Governance Queue Entry. The append-only
approval registry rejects replay and records forward revocation/supersession; only its latest
effective approval can support governance eligibility.

## Immutable outputs and replay

Every policy, approval, gate set, evidence record, readiness report, manifest, release
request, result, registry entry, and registry snapshot has a deterministic canonical
identity. Contracts reconstruct nested inputs to detect tampering. The append-only
Deployment Registry accepts governance-certified results only, preserves predecessor
lineage, and returns the existing snapshot for an exact replay. Its documented uniqueness
key is `(candidate, artifact, target environment, runtime contract, deployment policy)`.
A later result with the same key must explicitly supersede the latest matching entry;
candidate deployment to a genuinely different artifact or environment is not conflated.

An eligible result emits a Deployment Readiness Report, a non-activating Deployment
Manifest, a Deployment Registry-compatible result, and a Release Request whose status is
`PENDING_PRODUCTION_RELEASE_AUTHORITY`. Invariants keep `activation_permitted`,
`deployment_performed`, `production_released`, and `trades_executed` false.
The readiness field is deliberately named `release_governance_eligible`, not `release_ready`.
Release Requests additionally keep production-release, runtime-activation, broker-access,
and trade-execution authorization false. Existing V27 remains the sole production executor.
