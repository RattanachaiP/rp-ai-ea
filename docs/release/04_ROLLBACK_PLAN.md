# Rollback Plan

## Objective and authority

Rollback restores the **previous certified release**—never an ad hoc rebuild,
working-tree state, or partially repaired candidate. Before deployment, the
release manager must record the previous release tag/commit, artifact and
configuration digests, backup location, restoration commands, responsible
operator, and validation owner. If no previous certified release is available,
deployment is prohibited.

The incident commander authorizes rollback. The operator executes it; an
independent validator confirms restoration. Safety takes priority over
continuing execution.

## Common rollback procedure

1. Declare the incident, stop new activation/submission, and record UTC time,
   candidate digest, UUIDs, broker state, terminal state, and diagnostics.
2. Quiesce the candidate using the approved operational stop procedure. Do not
   delete or edit evidence and do not blindly resubmit an uncertain order.
3. Reconcile open orders, deals, and positions with the broker. Escalate any
   indeterminate exposure for controlled manual handling under operational
   authority.
4. Preserve candidate logs, packages, configuration, repository digest, and a
   digest manifest in the incident record.
5. Restore the previous certified artifact and its matching configuration from
   the immutable release store; verify both digests before activation.
6. Start using the previous release's approved startup procedure. Verify
   diagnostics, repository/artifact identity, connectivity, UUID state, and the
   activation invariant before enabling submissions.
7. Reconcile broker and local state again. Validate that there are no duplicate
   orders, orphaned positions, or unresolved packages.
8. Record PASS/FAIL for restoration checks. Keep production stopped on any
   FAIL. Close rollback only after the independent validator records PASS.

## Trigger-specific containment

| Trigger | Immediate containment | Required restoration verification |
|---|---|---|
| Bad deployment | Stop activation and submissions; preserve deployment manifest. | Previous artifact/configuration digests and governed startup checks match. |
| Runtime corruption | Isolate the runtime and corrupted state; snapshot before recovery. | Restore last certified state/backup, then prove state and broker reconciliation. |
| Invalid package | Quarantine package by digest; do not edit or replay it. | Previous package contract/digest is restored and no invalid UUID remains pending. |
| Reader failure | Stop publication/activation path and preserve unread package/state. | Previous reader consumes only valid governed packages without duplicate processing. |
| Bootstrap failure | Keep activation disabled; capture startup diagnostics. | Previous bootstrap completes every prerequisite before activation. |
| Executor rejection | Stop automated retries and correlate broker response to UUID. | Broker/local state is reconciled; previous executor is restored without replaying the rejected package. |

## Roll-forward prohibition

A rollback incident cannot be closed by labeling a patched candidate as the
previous certified release. Any fix follows a new reviewed candidate and the
full gate and approval process. Rollback success restores service eligibility;
it does not certify the failed candidate.
