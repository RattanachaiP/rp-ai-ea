# RAIP V1 Architecture

RAIP V1 is a disabled-by-default, passive observer. It reads copies of closed-trade export records supplied to `EventCollector`; no runtime, bridge, executor, dashboard, broker, or MT5 module imports RAIP. The collector serializes observations, the builder creates one immutable completed-trade snapshot, and the report builder aggregates snapshots only.

Data flow: exported record copy → JSONL event → closed-trade snapshot → daily factual review. RAIP failures are caught internally and quarantined/logged; trading callers must not await it.

No deployment integration is included. Enablement requires a future separately reviewed integration that constructs `ReviewEngineConfig(enabled=True)`. Rollback is to leave it disabled or remove its independent review-data directory; it neither changes nor locks canonical trading files.
