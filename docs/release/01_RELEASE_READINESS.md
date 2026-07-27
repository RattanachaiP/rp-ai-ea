# PR227 Production Release Readiness

## Purpose and boundary

This document establishes measurable release gates for release candidate
`v27.0.0-rc1`. PR227 is a governance change only: it does not certify Live
readiness, change runtime behavior, or authorize a production deployment.

The certification vocabulary is deliberately narrow:

| Area | PR227 state | Meaning |
|---|---|---|
| Architecture | **CERTIFIED** | The architecture baseline through PR226 remains the governed baseline; PR227 changes no ownership. |
| Runtime | **GOVERNED** | Runtime integrity has defined, binary checks; this is not operational certification. |
| Documentation | **COMPLETE** | The production-readiness framework is defined by this directory. |
| Production release | **BLOCKED** | Required MT5 Demo operational evidence is not complete. |
| Release candidate plan | **READY** | The identifier `v27.0.0-rc1` is reserved for the candidate process only. |

## Decision rule

A gate is satisfied only when every check in that gate is **PASS** and its
evidence is recorded in the release record. Missing, stale, ambiguous, or
unreproducible evidence is **FAIL**. Gate D is mandatory. A production release
requires Gates A, B, C, and D and every approval in
`06_RELEASE_APPROVAL.md`. There are no waivers, assumed passes, or partial
passes.

## Release gates

### Gate A — Repository Integrity

| Check | PASS evidence | FAIL condition |
|---|---|---|
| Clean working tree | Captured `git status --porcelain` output is empty at the candidate commit. | Output is non-empty or absent. |
| Synchronized | Local candidate commit equals the reviewed, protected remote candidate commit; both hashes are recorded. | Hashes differ or either hash is absent. |
| Deterministic build | Two clean builds from the same commit and pinned toolchain produce identical artifact digests. | Digests differ, dependencies/toolchain are unpinned, or evidence is absent. |

### Gate B — Architecture Integrity

| Check | PASS evidence | FAIL condition |
|---|---|---|
| Ownership preserved | Reviewed diff and ownership map show no transfer or duplication of component responsibility. | Ownership changes, overlaps, or review is absent. |
| Single authority | Trace and review show exactly one authoritative publisher/decision source for each governed contract. | Multiple or indeterminate authorities exist. |
| Immutable package | The consumed execution package is digest-identified and cannot be mutated after publication. | The package changes after publication or its digest is absent. |

### Gate C — Runtime Integrity

| Check | PASS evidence | FAIL condition |
|---|---|---|
| Runtime diagnostics | Governed diagnostics are captured for startup, steady state, and failure handling. | Required diagnostics are absent or indicate failure. |
| UUID lineage | One UUID is traceable without a break across publication, consumption, and execution evidence. | The UUID is missing, changes unexpectedly, or cannot be correlated. |
| Repository digest | Runtime evidence identifies the exact repository digest under certification. | Digest is absent or does not equal the candidate commit. |
| Activation invariant | Evidence proves activation occurs only after all governed prerequisites succeed. | Activation precedes a prerequisite, occurs after a failure, or is unproven. |

### Gate D — Operational Evidence (**required**)

All evidence must come from a real MT5 Demo end-to-end run against the exact
candidate digest. Simulator, mock, unit-test, and narrative evidence cannot
satisfy this gate.

| Check | PASS evidence | FAIL condition |
|---|---|---|
| MT5 Demo | Account/server identity is redacted as needed but demonstrably Demo, with timestamps and candidate digest. | Demo environment is unproven. |
| Broker | Broker request and response identifiers, timestamps, and result codes correlate to the candidate UUID. | Broker correlation is incomplete or absent. |
| OrderSend | Actual request, response, return code, order/deal identifiers, and terminal logs are captured. | Any required field is absent or the send is simulated. |
| Lifecycle | Evidence covers decision through submission, acceptance/rejection, position handling, and terminal closure/state. | Any lifecycle phase is missing. |
| Restart recovery | A controlled restart demonstrates reconciliation without duplicate or orphaned execution. | Recovery is not run or produces duplication, orphaning, or inconsistent state. |
| Latency | Timestamped stage measurements and the approved threshold are recorded; every measurement meets it. | Threshold is missing, measurements are missing, or any measurement exceeds it. |

## Current release decision

Demo Operational Certification is **NOT COMPLETE**. Therefore Gate D is
**FAIL** and the Production Release is **BLOCKED**. PR227 provides no evidence
that changes that result. PR228 is the planned evidence-collection activity.

No final version tag may be created and no production release may be
published. Preparing `v27.0.0-rc1` does not imply production or Live approval.
