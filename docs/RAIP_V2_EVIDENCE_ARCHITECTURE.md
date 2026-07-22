# RAIP V2 — Review & Evidence Engine

## Boundary and ownership
RAIP V2 is a passive, post-completion observer. It reads immutable V1 snapshots and writes only under the configured review data root: `evidence/` and `intelligence/`. It does not import, call, or modify the decision writer, runtime payload, executor, broker safety, recovery, thresholds, confidence, or any MT5-facing component.

## Deterministic evidence flow
`immutable snapshot -> deterministic classifier -> reproducible scoring -> immutable evidence -> daily intelligence`

The classifier uses only explicit snapshot fields and a fixed priority: NEWS, REVERSAL, BREAKOUT, PULLBACK, CONTINUATION, RANGE, TREND, UNKNOWN. The scoring engine is pure and derives the eight required metrics from snapshot outcome/execution fields. Evidence identity is SHA-256 of schema version, trade id, and snapshot hash; an existing identity is never overwritten.

## Storage and recovery
Evidence writes use `.tmp`, `fsync`, and atomic hard-link creation. A restarted processor regenerates the same identity and treats the existing evidence record as successfully completed. Daily intelligence writes use `.tmp`, `fsync`, then atomic rename. Failed processing remains isolated to the evidence layer; it can be retried without changing trading behavior.

## Daily intelligence
`daily_intelligence.json` contains trade count, win rate, average RR, average confidence, classification distribution, entry/exit averages, evidence generated, and processing errors. It is descriptive only: it emits no recommendation, learning, optimization, or execution instruction.
