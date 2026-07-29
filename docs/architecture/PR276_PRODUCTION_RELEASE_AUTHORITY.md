# PR276 Production Release Authority

## Final governance boundary

PR276 establishes the final governance authority before Production Runtime. The authority
consumes only the Deployment Readiness Report, Deployment Manifest, Release Request, Human
Approval Record, Release Policy, and a canonical assessment timestamp. It does not train,
evaluate, qualify, promote, deploy, access a broker, execute trades, or modify strategy or
learning. Its outputs are immutable governance records, not executable runtime machinery.

The input bundle binds the exact identities of all five authoritative inputs. A missing or
malformed input is rejected at the bundle boundary; an intact but ineligible or mismatched
input produces a fail-closed `PRODUCTION_RELEASE_REJECTED` decision.

## Eight release gates

1. Deployment readiness
2. Human approval
3. Release policy
4. Release manifest integrity
5. Artifact integrity
6. Runtime compatibility
7. Rollback readiness
8. Final governance certification

Every gate must pass. Final certification also requires the deployment evidence chain's
registry-lineage gate and its authoritative registry identities. Artifact certification is
bound to the deployment artifact identity, package and model hashes, and build provenance.
Runtime certification binds one target environment and accepted runtime contract. Rollback
certification binds a content-addressed rollback artifact and rollback plan.

## Sole activation authorization

An approved decision emits one Release Certificate, one Release Manifest, and one Runtime
Activation Authorization. Only `runtime_activation_authorized` is true. Broker access,
trade execution, deployment, training, evaluation, qualification, and promotion remain
false. Rejected decisions emit none of these three outputs.

The append-only Release Registry verifies predecessor lineage and accepts approved decisions
only. Exact replay is idempotent. The registry rejects a second distinct certificate for the
same `(release request, deployment manifest, target environment, runtime contract)` activation
scope, ensuring exactly one certificate can authorize a Production Runtime activation.

All policies, bundles, gate evidence, certificates, manifests, authorizations, decisions,
registry entries, and registry snapshots have deterministic content identities. Nested
contracts are reconstructed at trust boundaries so mutated or forged identity-bearing data
fails closed.
