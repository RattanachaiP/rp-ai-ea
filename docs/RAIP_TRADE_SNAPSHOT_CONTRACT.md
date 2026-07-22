# RAIP Trade Snapshot Contract

A snapshot requires exactly one `TRADE_CLOSED` event and stable `trade_id`. Its path is immutable: `snapshots/YYYY/MM/DD/trade_<trade_id>.json`. A byte-equivalent replay is idempotent; a different snapshot for the same ID raises a conflict rather than overwriting evidence.

Commission, swap, gross profit, and net profit preserve source semantics without recomputation: a future adapter must document whether costs are signed before publishing its source records. Missing evidence stays `null`; MAE/MFE are never inferred.
