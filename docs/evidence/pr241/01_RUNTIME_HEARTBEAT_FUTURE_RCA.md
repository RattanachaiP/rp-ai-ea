# PR241 — Runtime Heartbeat Future Validation Investigation

Date: 2026-07-28 (UTC)

## Scope and conclusion

This investigation makes **no behavioural change**.  The rejection is an exact,
zero-tolerance comparison: the collector reads `now = time.time()`, converts the
payload heartbeat to `float`, computes `age = now - heartbeat`, and raises
`MARKET_STATE_HEARTBEAT_FUTURE` whenever `age < 0.0`.  It is therefore equivalent
to `float(heartbeat_unix) > time.time()` for the two values captured in that read.

The tracked producer supplies `heartbeat_unix` from MQL5 `TimeCurrent()`, i.e. the
trade-server clock used by the tick-driven writer.  The consumer supplies `now`
from Python `time.time()`, i.e. the host wall clock.  The clocks are independent.
This is not a millisecond conversion: both values are seconds, and the code does
not multiply or divide either value.  `time.monotonic()` is used only for read
latency, sampling-window duration, and sleep scheduling.  UTC conversion occurs
only while rendering diagnostic timestamps and does not participate in freshness
validation.  No timezone conversion is applied to the producer value.

## Actual code path

1. Development startup delegates directly to production startup.
2. Production startup resolves the canonical market-state path and constructs
   `GovernedEnvironmentObservationProducer`.
3. `collect()` reads and parses the JSON, then verifies producer identity.
4. It samples Python `time.time()`, reads numeric `heartbeat_unix`, computes the
   signed age, and immediately fails closed if the age is negative.
5. A duplicate is classified only after freshness validation.  Consequently an
   unchanged publication may be reported as a duplicate while the next newly
   published sequence fails the preceding future check.

## Time-source matrix

| Item | Actual source | Unit / kind | Conversion and timezone |
|---|---|---|---|
| heartbeat | Writer `now = TimeCurrent()`; cast to `long`; emitted as `heartbeat_unix` | integer seconds; trade-server wall clock | no offset or unit conversion |
| validation local clock | injected `clock`, default `time.time` | floating-point seconds; host Unix wall clock | none |
| sampling and latency | injected `monotonic`, default `time.monotonic` | floating-point monotonic seconds | never compared with heartbeat |
| diagnostic timestamp | `datetime.fromtimestamp(..., timezone.utc)` | UTC display only | rendering after/beside validation |

## Diagnostic evidence status

The repository/container contains neither the live `market_state.json` nor logs
with numeric values for sequences 39689 and 39690.  The supplied observation gives
the sequence and reason, but not the two clock readings.  It would be fabrication
to report `heartbeat_unix`, `local_time`, or `delta_seconds` for that incident.
Therefore **clock skew is not confirmed by the available runtime evidence**.

The controlled regression evidence establishes the sign boundary, not the live
root cause: a heartbeat of `1001.0` against local time `1000.0` is rejected, while
the existing accepted samples are non-future.  The read-only diagnostic
`analysis/heartbeat_future_diagnostic.py` captures multiple live observations and
records:

* `heartbeat_unix`
* midpoint `local_time`, bounded by timestamps immediately before and after read
* signed `delta_seconds = heartbeat_unix - local_time`
* sequence and read-time uncertainty

Run it on the canonical shared file while the writer is publishing:

```text
python analysis/heartbeat_future_diagnostic.py <market_state.json> --count 10 --interval-seconds 0.25
```

Interpret a delta as genuinely positive only when `heartbeat_unix` is also later
than `local_time_after_read`; values within the before/after interval are subject
to read/publication timing.  Stable positive deltas across advancing sequences
indicate clock-source offset/skew.  A near-integral factor of 1,000 indicates unit
conversion, which the tracked code itself does not perform.  Sporadic bounded
deltas indicate publication/read timing.  Sequence 39690's actual classification
cannot be selected among these cases until this capture is obtained.

## Root Cause Analysis

### Confirmed implementation cause

The immediate cause of the exception is a negative computed age under a strict
zero-tolerance policy.  The architecture-relevant implementation risk is that the
producer and validator compare independent trade-server and host wall clocks while
declaring no allowed offset.  There is no race in the arithmetic and no implicit
timezone or millisecond conversion in the Python path.

### Incident root cause pending live evidence

Whether sequence 39690 was ahead because of genuine future dating, ordinary clock
skew, the semantics of `TimeCurrent()`, or publication timing remains unproven.
The prior acceptance and duplicate rejection of 39689 do not prove synchronization:
a newly published integer-second heartbeat can cross ahead of the host clock while
an older heartbeat remains non-future.

## Architecture-compliant recommendation

1. Capture at least ten advancing publications with the diagnostic above and retain
   its JSON Lines output alongside host clock-synchronization and broker-server-time
   evidence.
2. Make no Runtime policy change until the live delta distribution identifies the
   cause.  In particular, do not relabel or bypass the current fail-closed rejection.
3. If normal bounded skew is confirmed and Architecture approves a policy change,
   introduce a separately reviewed immutable/configurable policy field such as
   `max_clock_skew_seconds`, validate it as finite and non-negative, include it in
   the policy payload/digest/UUID, document its clock semantics, and reject only
   when `heartbeat_unix > current_time + max_clock_skew_seconds`.
4. Derive the configured value from measured evidence; do not hard-code a magic
   tolerance.  Submit that behavioural modification as a separate PR with boundary,
   fail-closed, and exact-threshold tests.

No change is recommended to AI Decision, Strategy, Bias, Risk, Executor, Broker
Safety, OrderSend, Execution Confidence Integration, or the existing fail-closed
Runtime behavior in PR241.
