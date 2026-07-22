# RAIP Data Retention, Operations, and Rollback

`events`, `snapshots`, and `daily` are append-only review evidence. Rejected records are quarantined separately and should be reviewed before deletion according to the deployment's retention policy. Collector state, when added by a deployment poller, must be stored only under `runtime/collector_state.json` and must never modify source artifacts.

RAIP is disabled by default (`ReviewEngineConfig.enabled=False`). To enable, configure a separate review-data root and read-only copy/export source paths. To roll back, set `enabled=false` and stop the observer; no trading artifact or runtime behavior needs restoration because RAIP never writes to them. Atomic `.tmp` writes, flush/fsync, and rename prevent partially readable snapshots. A host crash before rename may lose the pending observation, so source exports must remain available for replay.
