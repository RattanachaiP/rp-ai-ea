# RAIP V1 passive architecture

`TradeSource -> EventCollector -> EventQueue -> TradeSnapshotBuilder -> SnapshotRepository -> DailyReviewBuilder`.

The collector only reads exported records and emits normalized events. It neither imports snapshot/review code nor writes snapshots. The default configuration has `enabled=False`; RAIP has no runtime, bridge, MT5, executor, broker-safety, order-manager, or deployment dependency. Failures stay within the caller of this optional observer.

CSVTradeSource reads a supplied exported CSV read-only. ReplayTradeSource accepts copied records for deterministic testing. Stable `trade_id` is mandatory before snapshot creation; source correlation values are retained verbatim. Commission and swap are preserved as source-provided signed account-currency values; no accounting semantics are inferred.

Snapshots are atomic, append-only, and conflict on different existing contents. Exact replay is idempotent. Roll back by keeping RAIP disabled or removing its review-data root: it never changes trading artifacts. Restart safety comes from idempotent snapshot filenames, although events unavailable from an upstream source before collection are not recoverable.
