# PR231 — Runtime Environment Observation Bring-Up

## Flow and complete call path

```text
MT5 terminal
  └─ RP_Market_State_Writer_V14...mq5::OnTick
       └─ atomic market_state.json publication (sequence + heartbeat)
            └─ python -m runtime.production_startup::main
                 └─ GovernedEnvironmentObservationProducer.collect
                      ├─ identity, freshness, schema, telemetry and uniqueness checks
                      ├─ GovernedEnvironmentObservation (ten dimensions)
                      └─ GovernedProductionStartup.start
                           └─ ProductionExecutionInitializer.start
```

The operator-facing caller is `runtime.production_startup.main`. It collects before
constructing `ProductionStartupConfiguration`; therefore the decision reader,
recommendation pipeline, executor, and broker cannot run when collection fails. The
collector samples for five seconds at 50 ms intervals and requires **three** unique
sequence IDs. Every accepted publication must have the exact XAUUSD producer,
producer-version, schema and source UUID; a heartbeat no more than five seconds old
and no more than the immutable policy's `max_clock_skew_seconds` ahead of the host
clock; a
non-negative integer sequence; a positive bid; non-negative spread and slippage; and
session/liquidity quality in `0..1`. Unique samples must be strictly sequence-ordered.
The readiness thresholds remain owned by PR187 and are unchanged.

## Required observations and lifecycle

All ten values are produced together by `GovernedEnvironmentObservationProducer` and
persisted downstream by the PR187 execution-environment repository under
`learning_data/execution_environment`. They refresh on each governed startup from a
new five-second window; no stored value is reused. The source heartbeat expires after
five seconds, so a stored prior environment record is lineage evidence, not a startup
cache.

| Observation | Authentic producer/source | Aggregation in the five-second window |
|---|---|---|
| feed stability | collector read result | successful reads / attempts |
| price-stream continuity | Writer `sequence_id` | progressing transitions / transitions |
| market-session quality | Writer governed telemetry | minimum |
| spread quality | Writer live bid/ask telemetry | maximum points |
| latency quality | collector monotonic file-read measurement | maximum milliseconds |
| slippage expectation | Writer live-tick EWMA policy | maximum points |
| market-liquidity quality | Writer governed telemetry | minimum |
| environment consistency | Writer sequence/heartbeat pairs | progressing pairs / transitions |
| data freshness | Writer `heartbeat_unix` and collector wall clock | maximum non-negative age; accepted clock skew reports zero age |
| environment completeness | collector required-field validation | complete reads / attempts |

## Root cause and correction

PR230 proves that collection made zero successful observations because its configured
path did not contain a Writer publication. The V26 decision runtime already supports
the deployment override `RP_AI_SHARED_ROOT`, but the earlier observation preflight
used an import-time, hard-coded Windows Common Files path. Thus an operator could
correctly point the runtime at a transported/shared publication while startup sampled
a different path. This was a reader-path wiring defect, not an observation-repository
or uniqueness-policy defect.

PR231 resolves the observation path at command execution. When
`RP_AI_SHARED_ROOT` is set, both preflight and V26 consume
`$RP_AI_SHARED_ROOT/XAUUSD/market_state.json`; otherwise the existing canonical
Common Files location remains the fail-closed default. No threshold, validation,
decision, executor, broker, or Writer contract changed.

## Observation diagnostics

Collection now emits a structured `ENVIRONMENT_OBSERVATION` log event for every
unique accepted publication, duplicate or malformed rejection, terminal gate
rejection, and completed observation window. Events carry observation UUID,
UTC timestamp, path/source, SHA-256 digest, status, reason and sequence when those
values can be authenticated. A completed window also stores its deterministic UUID
and digest on `GovernedEnvironmentObservation`. Missing or malformed candidates use
null identity/digest rather than inventing identity.

## Runtime evidence and verified sequence

The checked-in PR230 runtime log is the authentic negative control: the Writer
publication was not received, collection stopped with
`INSUFFICIENT_UNIQUE_ENVIRONMENT_OBSERVATIONS`, and no downstream component ran.
PR231 regression evidence verifies the repaired path convergence and exercises three
advancing contract-valid publications through the unchanged gate. This executable
test is not represented as live MT5 evidence. A production-online claim still
requires running the following on the MT5-connected deployment host and retaining
the emitted diagnostics:

```powershell
$env:RP_AI_SHARED_ROOT = 'D:\RP_AI_EA\shared'
python -m runtime.production_startup
```

Expected diagnostics are three or more `UNIQUE_FRESH_PUBLICATION` acceptances,
`OBSERVATION_WINDOW_COMPLETE`, and then the governed production-startup stages. If
the first event is unreadable, the Writer/transport/path is the failing component; if
identity/freshness/telemetry is rejected, the publication is the failing component;
if the window completes but PR187 refuses readiness, the logged ten observations
identify the environmental threshold that failed.
