# V27.6 Writer Integration Report

## Ownership
`bridge/decision_writer.py` is a runtime consumer only. It reads the publisher-owned `decision.json`, validates it, and exposes the unchanged document to the Executor. The Brain remains the sole authority for trading intent.

## Validation pipeline
The bridge evaluates independent stages in this order: JSON decoding, exact-schema validation, sequence validation, heartbeat validation, and executable-contract validation. Any failed stage returns a locally constructed safe result: `decision=WAIT`, `fail_safe=true`, and `executable=false`.

## Schema policy
Only published schema version `2.0` is accepted. The document must contain exactly the runtime publication fields; missing, extra, or wrongly typed fields are rejected as unknown/malformed runtime structure.

## Heartbeat policy
`heartbeat_unix` is compared with an injected clock. The default maximum age is 30 seconds and is configurable through `heartbeat_max_age_seconds`. A configurable two-second `allowed_future_skew_seconds` allowance rejects materially future-dated publications. Both duration settings and injected clock output must be finite, non-negative numeric values (and cannot be booleans). Expired or excessively future-dated publications are never forwarded.

## Sequence policy
The bridge tracks its most recently accepted sequence ID. Higher IDs are accepted, identical IDs are ignored without execution, and lower IDs fail safe as stale.

## Executable contract
The bridge treats `executable` exclusively as a publisher-owned boolean and validates its publisher contract. When true, the document must carry a matching BUY/SELL direction, entry permission, `ENTRY_ALLOWED`, an allow action, and no fail-safe flag. A fail-safe document must be the canonical non-executable WAIT shape. It does not derive executability from confidence, probability, scores, direction, or any other analytical value. `false` stays non-executable.

## Legacy compatibility
`WriterReadResult.legacy_payload` provides a direct-name mapping (`bias`, `allowed`) for an older Executor while retaining `decision`, `executable`, and `fail_safe` verbatim. It creates no new decision and performs no reinterpretation.

## Explicit non-responsibilities
The writer does not calculate probability, expected value, ELI, APC, confidence, scores, direction, BUY/SELL, WAIT/BLOCK overrides, or budgets. It imports no Brain module and does not call a decision pipeline.

## Next phase: Executor Integration
Connect the Executor only to accepted `WriterReadResult.payload` (or the direct legacy mapping where required). It must skip all results that are not accepted, are duplicates, or have `executable=false`.
