# RAIP V6 Governance Engine

V6 is an independent, asynchronous, observation-only auditor of the passive RAIP chain:
`Snapshot -> Evidence -> Knowledge -> Insight -> Recommendation`. It is deliberately isolated
from `bridge`, `runtime`, MT5, Writer, Executor, Broker Safety, risk, decision publication, and
all trading payloads. A governance error is logged and surfaced in health output; it never blocks,
changes, or delays trading.

## Monitors and outputs

`GovernanceCoordinator` atomically publishes deterministic JSON below the isolated review-data
root: `governance/boundary/boundary_health.json`, `governance/health/schema_health.json`,
`governance/integrity/repository_health.json`, `governance/lineage/lineage_health.json`,
`governance/performance/performance_health.json`, and `governance/health/governance_report.json`.
Every output includes the common RAIP metadata plus `governance_version` and baseline commit
`b108658`. JSON is written to `.tmp`, fsynced, and renamed into place.

The history repository is separately append-only at
`governance/history/<report_id>/governance_repository.json`; a pre-existing report ID is returned
without rewrite. It records report ID, timestamp, platform status, detected issues, warning count,
producer, and schema version.

## Health semantics

A layer is Healthy only when all boundary, schema, repository, lineage, and performance monitors
pass. The boundary monitor statically rejects RAIP imports of trading packages; schema integrity
requires `schema_version`, `producer`, `owner`, and `created_at`; repository integrity checks IDs,
references, JSON/hash integrity; lineage checks the complete backward chain. Governance does not
repair detected problems and reports a stable content-addressed report ID instead.
