# PR232 Root Cause

## Failing invariant

The unchanged Environment Observation policy requires at least three authentic, identity-valid, unique, fresh Writer publications during the canonical observation window. Zero were accepted.

Exact terminal invariant: `INSUFFICIENT_UNIQUE_ENVIRONMENT_OBSERVATIONS`.

## Owning boundary

- Validation owner: `runtime.environment_observation.GovernedEnvironmentObservationProducer`
- Operational producer/path owner: canonical MT5 V14 Writer and its MT5 Common Files deployment
- Startup composition owner: `runtime.production_startup`

## Evidence-based cause

`RP_AI_SHARED_ROOT` was unset, so the reader correctly selected the canonical Windows Common Files fallback. This Linux container has no authenticated MT5 Demo terminal publication at that path and no `market_state.json` was found under the inspected accessible deployment roots. Every read attempt was consequently rejected as `UNREADABLE_OR_MALFORMED_PUBLICATION` before the terminal minimum-observation rejection.

This is an unmet operational precondition, not evidence of a remaining PR231 path-resolution code defect. The execution environment cannot prove that an MT5 terminal is authenticated, that the V14 Writer is attached, or that it is continuously publishing.

## Correction decision

No code correction was made. Changing validation, lowering the threshold, injecting observations, redirecting to a fixture, or bypassing startup would violate the task and architecture. The compliant remediation is to rerun this exact command on the authenticated Windows MT5 host with either:

1. the Writer using its default Common Files path and `RP_AI_SHARED_ROOT` unset; or
2. the Writer using `AbsoluteBridgeRoot` and `RP_AI_SHARED_ROOT` set to that exact same shared root.

Because no software defect was established, no new regression test was added.
