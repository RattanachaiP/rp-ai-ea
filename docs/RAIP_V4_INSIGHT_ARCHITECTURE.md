# RAIP V4 Insight & Learning Readiness Layer

## Scope and safety

The Insight Layer is a passive, read-only transformation: `Snapshot -> Evidence -> Knowledge -> Insight`.
It only reads immutable Knowledge documents and writes under the review-data root (`insights/`, `executive/`, `reports/`, and `ranking/`). It has no imports from the trading runtime and never reads or writes decision, execution, confidence, threshold, strategy, Writer, Executor, or Broker Safety data.

## Processing and storage

`InsightCoordinator` runs asynchronously after successful Knowledge publication. Failures are logged through the future callback and do not affect evidence collection, knowledge generation, or trading. On restart it finds the newest Knowledge version and safely regenerates the same versioned Insight; duplicate publication preserves the original bytes.

Each report is deterministic for a Knowledge version and includes schema, producer, owner, creation time, Knowledge version, and Insight version. The repository adds an `insight_id`. Files are published using exclusive `.tmp` write, `fsync`, atomic rename publication, then temp cleanup. Existing records are never overwritten.

## Intelligence outputs

Pattern rankings provide profit-factor, average-RR, and win-rate ordering. Session intelligence ranks ASIA, LONDON, NEW_YORK, and OVERLAP using win rate, profit factor, average RR, holding-time when provided by Knowledge, drawdown, and trade count. Market-state summaries cover TREND, RANGE, TRANSITION, VOLATILE, and NEWS. Confidence analysis exposes calibration drift and over/under-confident zones as observations only; it never changes runtime confidence.
