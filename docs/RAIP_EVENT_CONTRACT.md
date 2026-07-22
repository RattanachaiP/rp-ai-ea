# RAIP Event Contract

The canonical Sprint 1 envelope is `review_engine/schemas/event.schema.json`. Source artifacts are **copies** of already-exported lifecycle records, supplied by a future deployment adapter; Sprint 1 consumes no live MT5 or canonical trading file. `trade_id` must be a stable source-provided identifier on `TRADE_CLOSED`; correlation, candidate, sequence, series, and position IDs are copied when present and remain `null` otherwise.

Invalid JSON or invalid envelopes are written under `rejected/YYYY/MM/DD` with a machine-readable reason. Payload integrity is SHA-256 of canonical JSON.
