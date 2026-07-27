# Release Approval Matrix

## Approval rule

Approvals are sequential, explicit, named, dated, and bound to the candidate
commit, artifact digest, configuration digest, evidence manifest digest, and
approval role. An approver records exactly **APPROVED** or **REJECTED**. A
blank, conditional statement, verbal acknowledgement, or approval for another
digest is a missing approval.

Production approval may be considered only after all preceding approvals and
Gates A–D are PASS. If any required approval is missing or rejected, Release
Status is **NOT APPROVED**.

## Required matrix

| Order | Approval | Accountable decision | Required basis | PR227 state |
|---:|---|---|---|---|
| 1 | Architecture | Architecture authority confirms ownership, single authority, and immutable-package boundaries. | Gate B PASS and reviewed candidate diff | **MISSING** |
| 2 | Runtime | Runtime authority confirms diagnostics, UUID lineage, repository digest, and activation invariant. | Gate C PASS evidence bound to candidate | **MISSING** |
| 3 | Operational | Operations authority confirms scenario execution, recovery, reconciliation, and latency results. | Gate D PASS evidence bundle | **MISSING** |
| 4 | Demo Evidence | Independent evidence reviewer confirms authentic, complete, correlated MT5 Demo evidence. | Gate D manifest and independent review | **MISSING** |
| 5 | Production | Production release authority authorizes the exact candidate for production. | Gates A–D PASS and approvals 1–4 | **MISSING** |

## Approval record template

| Field | Value |
|---|---|
| Candidate version | `v27.0.0-rc1` |
| Candidate commit | `<full commit hash>` |
| Artifact digest | `<algorithm:digest>` |
| Configuration digest | `<algorithm:digest>` |
| Evidence manifest digest | `<algorithm:digest>` |
| Approval role | `<Architecture / Runtime / Operational / Demo Evidence / Production>` |
| Decision | `<APPROVED / REJECTED>` |
| Approver name/identity | `<identity>` |
| UTC timestamp | `<YYYY-MM-DDThh:mm:ssZ>` |
| Rationale / evidence reference | `<immutable reference>` |

## Current decision and version plan

All approval entries are currently **MISSING**. Demo Operational Certification
is **NOT COMPLETE**. Therefore:

- Release Status: **NOT APPROVED**
- Production Release: **BLOCKED**
- Final production tag: **PROHIBITED**
- Production publication: **PROHIBITED**
- Release candidate plan: **READY** as `v27.0.0-rc1`

The release manager may prepare the release candidate identifier after the
candidate commit is selected. This document does not create a Git tag. A final
release version may be planned only after every gate is PASS and all five
approvals are recorded.
