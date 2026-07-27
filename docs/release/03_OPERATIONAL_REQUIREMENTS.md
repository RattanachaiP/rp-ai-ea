# Operational Requirements

## Evidence controls

Operational certification must use the exact `v27.0.0-rc1` candidate commit
and artifacts. Every evidence bundle must include UTC timestamps, repository
commit, artifact/package digest, run identifier, terminal version, governed
configuration digest, and decision UUID. Secrets and account numbers may be
redacted, but the redaction must not prevent correlation or proof that the
account is Demo.

Evidence must be immutable, access-controlled, and retained with a manifest of
file digests. The operator and independent reviewer must be identified. A
rerun creates a new evidence bundle; it must not overwrite a failed run.

## Mandatory MT5 Demo scenario

The candidate must complete one controlled end-to-end scenario on MT5 Demo:

1. Record preflight health, terminal connection, Demo identity, repository
   digest, package digest, and absence of unresolved prior execution state.
2. Publish and consume one governed decision while preserving its UUID.
3. Submit the real `OrderSend` request and retain request parameters, UTC
   timestamp, broker response, return code, and order/deal identifiers.
4. Correlate broker acknowledgement or rejection to the same UUID. A rejection
   may test rejection handling, but does not substitute for the accepted-order
   lifecycle required for certification.
5. For an accepted order, record position state transitions and the final
   closed/terminal state, including broker identifiers.
6. Perform a controlled runtime/terminal restart at the approved lifecycle
   point; demonstrate reconciliation and recovery without a duplicate order,
   orphaned position, lost UUID, or divergent state.
7. Measure latency at decision publication, package availability, reader
   consumption, submission, broker response, and reconciliation. Record an
   approved maximum for each measured interval before evaluating the run.
8. Capture post-run diagnostics and verify that all local, package, executor,
   terminal, and broker states agree.

## Acceptance rules

- Every mandatory field and lifecycle phase must be present and correlated.
- Every broker/terminal result must be explicitly evaluated as PASS or FAIL.
- Every measured latency must be at or below its pre-approved threshold.
- Recovery must create no duplicate submission and leave no orphaned state.
- Runtime diagnostics must contain no unresolved integrity failure.
- Evidence from mocks, simulations, backtests, or non-Demo environments is
  supplemental only and cannot satisfy Gate D.

Any unmet rule makes the operational result **FAIL**. At PR227, the required
Demo evidence has not been collected, so Operational Certification is
**NOT COMPLETE** and Production Release remains **BLOCKED**.
