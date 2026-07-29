# PR275 Deployment Governance Authority

## Purpose and authority boundary

PR275 establishes the immutable governance boundary between an eligible promotion and a
future production-release authority. It validates and certifies release readiness; it does
not deploy or activate an artifact, alter Runtime or Strategy, access a broker, execute a
trade, or perform production release. A `ReleaseRequest` is an auditable request to the
separate release authority—not permission or executable release machinery.

The authority consumes only an identity-validated Promotion Registry entry, its exact
Promotion Report and Promotion Evidence, a Human Approval Record, and Deployment Policy.
It does not reconstruct training, evaluation, or qualification decisions.

## Eight deployment gates

1. Promotion eligibility
2. Human approval validation
3. Deployment policy validation
4. Evidence completeness
5. Registry lineage validation
6. Artifact integrity
7. Release readiness
8. Governance certification

All eight gates must pass. Policy mismatch, missing or rejected approval, broken registry
lineage, incomplete promotion evidence, or artifact/candidate identity mismatch produces
`DEPLOYMENT REJECTED`. Rejected results produce neither a manifest nor a release request.

## Immutable outputs and replay

Every policy, approval, gate set, evidence record, readiness report, manifest, release
request, result, registry entry, and registry snapshot has a deterministic canonical
identity. Contracts reconstruct nested inputs to detect tampering. The append-only
Deployment Registry accepts governance-certified results only, preserves predecessor
lineage, rejects candidate duplication, and returns the existing snapshot for an exact
replay.

An eligible result emits a Deployment Readiness Report, a non-activating Deployment
Manifest, a Deployment Registry-compatible result, and a Release Request whose status is
`PENDING_PRODUCTION_RELEASE_AUTHORITY`. Invariants keep `activation_permitted`,
`deployment_performed`, `production_released`, and `trades_executed` false.
