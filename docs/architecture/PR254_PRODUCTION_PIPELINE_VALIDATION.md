# PR254 — End-to-End Production Runtime Validation

PR254 is a read-only, post-event validator for an operator-selected continuous
Demo trace. The production host exports JSON Lines using schema
`PR254.PIPELINE_TRACE_EVENT.1.0`. Each event has a non-empty `lifecycle_id`, one
canonical stage, an explicit-offset `timestamp_utc`, and a `SUCCEEDED` or
`FAILED` status. A failed event has exactly one canonical failure classification.

The ordered stages are `MARKET_STATE`, `DECISION`, `PACKAGE`,
`EXECUTOR_ACCEPTED`, `ORDER_SENT`, `ORDER_FILLED`, `POSITION_CLOSED`,
`TELEMETRY`, and `ANALYTICS`. A lifecycle succeeds only when every stage is
present once, succeeded, and chronological. Missing stages become explicit
classified failures and are never silently ignored.

Stages form a causal prefix: no downstream stage may exist when an upstream
stage is absent, and an explicit failure is terminal for that lifecycle. The
stage-to-failure-class contract is fixed by the validator; arbitrary class and
stage combinations fail closed. Missing events prove interruption location but
not ownership, so they are classified `UNKNOWN`.

```bash
python -m analysis.production_pipeline_validation \
  --trace-events /operator/selected/pipeline_trace.jsonl \
  --output-directory /operator/selected/reports
```

The sole output is atomically replaced `pipeline_validation_report.json`, with
the source digest, aggregate metrics, end-to-end latency, missing-stage count,
and each lifecycle's timestamp and failure evidence. Raw lifecycle identifiers
are input-only and may encode sensitive trade, decision, order, deal, or position
identifiers; the report exports deterministic report-local ordinals only. Rates
are neutral observations: lifecycle failure rates deduplicate a class within a
lifecycle, while failure-event density counts every classified interruption.
PR254 defines no success threshold, pass/fail policy, promotion gate, or implied
production approval. Empty evidence fails with `EMPTY_PIPELINE_TRACE`.

The validator does not import, invoke, delay, retry, or modify any trading
subsystem. Atomic-write failures remove the temporary file and preserve any
previous valid report; there is no retry or remediation.
