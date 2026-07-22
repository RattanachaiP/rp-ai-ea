# RAIP V1 passive observer architecture

RAIP reads copies of already-exported, closed-trade evidence only. It owns append-only event files, immutable snapshots, quarantined invalid input, and factual daily reports. It is disabled by default (`ReviewEngineConfig.enabled=False`) and is not imported by `bridge`, `runtime`, or `mt5` execution paths.

`EventCollector.record` catches all observer errors and returns `False`; it does not block a caller. Snapshot storage writes a flushed temporary file and atomically renames it. Existing trade files are idempotent only for identical bytes; contradictory evidence is a conflict.

Source artifacts are supplied explicitly through `source_paths`; Sprint 1 does not poll or lock a canonical trading artifact. Stable source `trade_id` is required for a snapshot and event correlation fields are preserved verbatim. Commission and swap are treated as signed account-currency values only when calculating absent `net_profit`; an exported net value is otherwise preserved.

Rollback is configuration-only: leave `enabled` false or remove the review-data directory. No live trading configuration, order path, or broker interaction is changed. The observer has no functions to send, close, amend, cancel, or otherwise influence orders.
