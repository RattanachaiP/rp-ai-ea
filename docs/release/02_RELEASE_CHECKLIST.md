# Release Checklist — `v27.0.0-rc1`

## Use

The release manager must replace no status with prose. Each row is exactly
**PASS** or **FAIL**, and each **PASS** must cite retained evidence. Missing
evidence is **FAIL**. The current PR227 assessment records known evidence state;
it is not a Live-readiness claim.

| Gate | Checklist item | Current status | Evidence required for PASS |
|---|---|---:|---|
| A | Working tree is clean at certification | PASS | PR227 commit-time `git status --porcelain` capture |
| A | Candidate is synchronized to reviewed remote commit | FAIL | Matching local and protected-remote commit hashes |
| A | Build is deterministic | FAIL | Two clean build manifests with identical artifact digests |
| B | Architecture ownership is preserved | PASS | Governance-only candidate diff review |
| B | Each governed contract has a single authority | PASS | Approved architecture baseline and no ownership diff |
| B | Execution package is immutable and digest-identified | PASS | PR226 baseline review plus unchanged runtime diff |
| C | Runtime diagnostics satisfy governed checks | FAIL | Candidate-bound runtime diagnostics for the exact `v27.0.0-rc1` commit and artifact digest; PR224 baseline evidence alone is insufficient |
| C | UUID lineage is complete | FAIL | Candidate-bound UUID lineage for the exact `v27.0.0-rc1` commit and artifact digest; PR224 baseline evidence alone is insufficient |
| C | Runtime identifies repository digest | FAIL | Runtime evidence proving the exact `v27.0.0-rc1` candidate digest; PR224 baseline evidence alone is insufficient |
| C | Activation invariant is proven | FAIL | Candidate-bound activation evidence for the exact `v27.0.0-rc1` commit and artifact digest; PR224 baseline evidence alone is insufficient |
| D | Environment is verified MT5 Demo | FAIL | Real Demo account/server evidence |
| D | Broker interaction is correlated | FAIL | Broker request/response evidence |
| D | OrderSend is evidenced | FAIL | Real request, response, codes, and order/deal IDs |
| D | Complete execution lifecycle is evidenced | FAIL | Correlated lifecycle record through terminal state |
| D | Restart recovery is evidenced | FAIL | Controlled restart and reconciliation record |
| D | Latency is measured and within approved threshold | FAIL | Stage timestamps, threshold, and evaluated results |
| Approval | Architecture approval is recorded | FAIL | Named, dated approver decision |
| Approval | Runtime approval is recorded | FAIL | Named, dated approver decision |
| Approval | Operational approval is recorded | FAIL | Named, dated approver decision |
| Approval | Demo Evidence approval is recorded | FAIL | Named, dated approver decision |
| Approval | Production approval is recorded | FAIL | Named, dated approver decision after all other approvals |

## Binary outcome

- Gate A: **FAIL**
- Gate B: **PASS**
- Gate C: **FAIL** — governed PR224 baseline evidence exists, but candidate-bound runtime evidence for `v27.0.0-rc1` is absent
- Gate D: **FAIL**
- Approval matrix: **FAIL**
- Release Status: **NOT APPROVED**
- Production Release: **BLOCKED**

These statuses may change only in a reviewed release record containing the
required evidence. A failed row cannot be waived or described as “probably,”
“expected,” or assumed to pass.
