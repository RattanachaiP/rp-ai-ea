# RAIP Event Contract

Events are JSONL records with the Sprint 1 `1.0.0` envelope and SHA-256 of canonical JSON payload content. Event types are strictly allow-listed. Times are normalized UTC ISO-8601 strings. Invalid event data is quarantined with machine-readable failure information; collector failures return a failed RAIP result and do not propagate to a trading caller.

`trade_id` is taken from the stable closed-trade export identity (ticket/order/position mapping must be performed by the external exporter). Correlation identifiers are preserved exactly when published; RAIP never infers them.
