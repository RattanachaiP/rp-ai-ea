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

```bash
python -m analysis.production_pipeline_validation \
  --trace-events /operator/selected/pipeline_trace.jsonl \
  --output-directory /operator/selected/reports
```

The sole output is atomically replaced `pipeline_validation_report.json`, with
the source digest, aggregate metrics, end-to-end latency, missing-stage count,
exit-criteria result, and each lifecycle's timestamp and failure evidence. The
validator does not import, invoke, delay, retry, or modify any trading subsystem.
