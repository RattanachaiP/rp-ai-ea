# RAIP V1 architecture
RAIP is disabled by default and is a passive observer: it accepts copies of already-published evidence and writes only under `review_data`. It has no imports from `bridge`, `runtime`, or MT5 code and contains no order, position, decision, threshold, or deployment operation.

## Data flow and failure isolation
`TRADE_CLOSED` copy → validate/hash → append JSONL → build immutable snapshot → atomic RAIP-owned file → deterministic daily report. `EventCollector.collect` converts validation and IO failures into a rejected RAIP record, so callers need not wait for or act on RAIP.

## Configuration and rollback
Deploy only with an application-owned configuration specifying `enabled: false`, review root, conservative poll interval, read-only source paths, symbol allow-list, log level, strict schema mode, and quarantine policy. Roll back by disabling the caller/collector; no trading artifact is changed or locked.
