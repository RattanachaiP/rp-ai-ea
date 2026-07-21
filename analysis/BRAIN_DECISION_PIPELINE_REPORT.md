# Brain Decision Pipeline Orchestrator — V27.3 Report

## Scope and ownership

`brain/decision_pipeline.py` is the sole internal composition layer for the
approved Brain sequence. It invokes Probability, Expected Value, Entry Location
Intelligence (ELI), and the ELI-to-APC Entry Construction Coordinator in that
order. The coordinator remains the approved ELI/APC boundary: it delegates
winner-only position construction to APC and the pipeline does not duplicate
that allocation policy.

The pipeline validates outputs, aggregates them, and produces a pure domain
object. It does not calculate indicators, swings, ATR, risk/reward, or lots;
it does not publish a runtime file or contact Writer, Executor, MT5, or a
broker. In particular, this change does not write `decision.json`.

## DecisionPackage schema

`DecisionPackage` is a frozen internal object with:

- `direction`, `confidence`, `probability`, and `expected_value`;
- `location_score`, `entry_permission`, and `entry_state` from ELI;
- `construction_action` and total/used/remaining position budget from the
  coordinator/APC boundary;
- `decision` (`TRADE` only when the existing coordinator grants construction
  permission; otherwise `WAIT`); and
- an ordered immutable `decision_trace`.

`probability` is the Probability Engine's continuation-state probability. It
is retained as analytical telemetry and does not create a directional signal.
`confidence` is the pre-existing ELI input's execution-confidence value; the
orchestrator performs no confidence calculation.

## Trace and fail-safe behaviour

For a valid result the trace is deterministic and ordered as
`Probability`, `ExpectedValue`, `ELI`, `Coordinator`, then `APC`. It records
the existing modules' values/actions without recomputing them.

Every input/output contract violation or module exception produces a complete,
safe `DecisionPackage` with `decision=WAIT`, no entry permission, no action,
zeroed aggregate values, and one deterministic `FAIL_SAFE=<type>:<reason>`
trace item. It can never fall through to `BUY`, `SELL`, or `TRADE`.

## Future Writer integration

Writer integration is intentionally deferred. A separately approved adapter
may consume a validated `DecisionPackage`, but it must preserve this pipeline
as the sole Brain composition owner and must not make the domain object write
`decision.json` directly.
