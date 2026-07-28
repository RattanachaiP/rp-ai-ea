# PR242 — Runtime Clock Skew Policy

Date: 2026-07-28 (UTC)

## Architecture summary and boundary

PR242 is isolated to the Environment Observation policy and its collector. It does
not modify the AI Decision Engine, Strategy, Bias, Direction, Risk Construction,
Decision Publication, Execution Package, Writer, Executor, Broker Safety,
`OrderSend`, or Execution Confidence Integration. The observation gate remains
fail-closed: malformed, stale, identity-invalid, conflicting, insufficient, and
non-progressing publications are still rejected.

## Confirmed root cause

The MT5 Writer produces `heartbeat_unix` from the broker trade-server wall clock,
while Environment Observation validates it against Python host wall clock. The old
policy rejected every positive difference between these independent clocks. That
zero-tolerance comparison rejected legitimate bounded positive clock skew; it was
not a unit or timezone conversion problem.

## Immutable policy

`EnvironmentObservationPolicy.max_clock_skew_seconds` declares the largest accepted
positive difference between the Writer heartbeat and the collector's sampled host
time. Its governed default is **2.0 seconds**. It is a finite, non-negative `float`;
booleans, integers, negative values, NaN, and infinity are invalid and fail policy
construction. The field is part of the canonical policy payload and therefore
participates in both the SHA-256 policy digest and deterministic policy UUID. The
policy version is `PR187-OBSERVATION-POLICY.1.1`.

The exact comparison is:

```text
reject when heartbeat_unix > current_time + max_clock_skew_seconds
```

Equality is accepted. A heartbeat below the boundary is accepted. A heartbeat even
slightly above it is rejected as `MARKET_STATE_HEARTBEAT_FUTURE`. Accepted positive
skew is represented as zero seconds of data age so the existing `data_freshness`
dimension retains its documented non-negative semantics. The five-second stale
limit is unchanged and is evaluated against actual positive age.

## Regression and boundary evidence

The Environment Observation regression suite verifies acceptance at tolerance minus
epsilon, acceptance at exact equality, rejection above tolerance, deterministic
digest and UUID changes when tolerance changes, and fail-closed invalid policy
values. Existing coverage continues to verify duplicate sequences, stale
heartbeats, producer/source identity mismatches, and publication digest lineage.
No bypass, fallback, retry, clock rewriting, or hidden runtime constant was added.
