# RAIP V3 — Pattern Discovery Knowledge Layer

## Boundary

Pattern Discovery is a passive, read-only layer after immutable V2 Evidence:

`snapshot -> evidence -> asynchronous knowledge aggregation -> immutable knowledge files`

It imports no Writer, decision publication, Executor, Broker Safety, MT5, recovery, or strategy code. It cannot change confidence, thresholds, decisions, runtime payloads, or execution state. A knowledge processing failure is logged by the evidence coordinator's asynchronous callback; evidence creation and every trading path continue unaffected.

## Determinism and recovery

`PatternDiscoveryEngine` sorts evidence by `evidence_id`, uses fixed classification/session/state bucket orders, and creates `pattern_repository_version` from canonical source identity and statistics. Re-running against the same evidence yields the same version. `KnowledgeCoordinator.process_available()` rescans the evidence repository, so a restart safely regenerates or reuses the same repository version.

## Storage and immutability

For each content version `<digest>`, the repository creates these append-only files:

* `patterns/<digest>/pattern_repository.json`
* `statistics/<digest>/pattern_statistics.json`
* `knowledge/<digest>/knowledge.json`

Every file includes the required provenance metadata: `schema_version`, `producer`, `owner`, `created_at`, `source_schema_version`, `generated_from`, and `pattern_repository_version`. Repository records contain their pattern ID, classification, sample size, win rate, profit factor, average RR, confidence, creation timestamp, schema version, and owner.

Writes serialize canonical JSON to `.tmp`, flush and `fsync` it, then atomically publish with a hard link. Existing versions are never opened for writing or overwritten.

## Observations generated

The report contains statistics for the fixed eight pattern classifications, five sessions, and five market states. Confidence buckets from 50–60% through 90–100% compare recorded predicted confidence against actual outcomes. These reports are descriptive only; no calibration adjustment is performed.
