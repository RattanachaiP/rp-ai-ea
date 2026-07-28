# PR243 — Runtime Bring-up Continuation

## Runtime stage map

The governed operator path observed for this bring-up is:

`Market State Publication -> Environment Observation -> Decision Engine -> Decision Publication -> Execution Package -> Executor`

The trace stops at the first failed stage. A downstream stage is never reported as
entered or successful when its upstream dependency failed.

## Instrumentation

`RuntimeStageLifecycle` writes append-only JSON Lines. Every stage invocation has a
new UUID and emits `ENTER`, followed by exactly one `SUCCESS` or `FAIL`. Records carry
the stage name and UUID, start/end timestamps, duration, upstream dependency, failure
reason, exception type/message, and propagation path. A terminal failure additionally
emits `RUNTIME_TERMINATED`. The observer returns `False` from its context-manager exit
and therefore never swallows or replaces the originating exception.

The canonical development/production entrypoint applies this instrumentation at the
Environment Observation and Decision Engine transitions. Later stages are not entered
when the Decision Engine prerequisite fails.

## Observed runtime sequence

On 2026-07-28, a live atomic test publication advanced through sequence IDs 10, 12,
15, 17, 20, 22, and 24. Environment Observation completed successfully. The resulting
stage trace was:

```text
ENTER   Environment Observation (upstream: Market State Publication)
SUCCESS Environment Observation (duration: 301.779 ms)
ENTER   Decision Engine (upstream: Environment Observation)
FAIL    Decision Engine (ProductionStartupError: DECISION_INTELLIGENCE_ACTIVATION_MISSING)
RUNTIME_TERMINATED Decision Engine -> Environment Observation -> Runtime
```

Decision Publication, Execution Package, and Executor were not entered.

## First blocker and root cause

The first verified blocker after Environment Observation is **Decision Engine**. Its
canonical PR184 repository contained no owner-governed production-input activation
record. `ProductionStartupConfiguration.from_canonical_repository` therefore rejected
startup with `DECISION_INTELLIGENCE_ACTIVATION_MISSING`. This is a governed prerequisite
failure, not a decision-algorithm failure and not evidence that an activation should be
fabricated or selected by recency.

## Behaviour boundary

PR243 changes observation only. It does not modify decision, strategy, bias, direction,
risk construction, publication/Writer behaviour, Execution Package assembly, execution
confidence, Executor, broker safety, or `OrderSend`. Exceptions continue to propagate
unchanged and failed upstream dependencies still prevent downstream invocation.
