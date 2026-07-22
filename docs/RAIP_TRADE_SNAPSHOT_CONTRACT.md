# RAIP Trade Snapshot Contract

One immutable snapshot path is derived from the closed UTC date and a SHA-256-safe trade identifier. Existing paths are never overwritten. Replayed source event IDs return the original snapshot idempotently; a different source event for the same trade ID is reported as a conflict.

Commission and swap preserve exported signed account-currency values. Therefore RAIP does not recompute net profit: source `net_profit` remains authoritative. Missing optional evidence stays `null` and appears in `data_quality.missing_fields`; MAE/MFE are never estimated.
