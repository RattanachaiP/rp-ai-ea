# RAIP V1 passive architecture
`review_engine` reads copies of closed-trade exports through `TradeSource`. `EventCollector` only normalizes and appends event evidence; `SnapshotCoordinator` separately invokes `TradeSnapshotBuilder` and `SnapshotRepository`. Reports split loading, factual aggregation, and construction. RAIP imports neither `runtime`, `bridge`, nor MT5 code, and has no execution, decision-publication, position-management, or configuration-mutating API.

The default configuration is `enabled=False`. In that mode the collector does not read sources or write events, state, quarantine, snapshots, or reports. RAIP errors are contained by the collector and do not propagate to callers.
