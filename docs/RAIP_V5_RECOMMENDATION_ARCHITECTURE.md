# RAIP V5 Recommendation Layer

The V5 layer is a passive, asynchronous consumer of immutable V4 Insight reports. It aggregates all available Insight reports deterministically, then de-duplicates recommendation categories while retaining every contributing lineage ID. It has no imports from `bridge`, `runtime`, MT5, Writer, Executor, or Broker Safety and therefore cannot change trading latency or execution authority.

## Flow and safety gate

`Insight -> deterministic rules -> complete embedded lineage -> validation -> append-only repository -> audit`.

Insight preserves the immutable Knowledge-to-Evidence-to-Snapshot lineage. The recommendation generator consumes that Insight document only. A missing Knowledge ID, Evidence ID, or Snapshot ID raises `LINEAGE_INCOMPLETE`; validation failures are logged and never published. Recommendations are advisory-only and historical impact values explicitly carry `not_guaranteed_future_performance: true`.

## Stored files

Each content-addressed recommendation version is atomically written (`.tmp`, fsync, rename) once under isolated review-data folders:

* `recommendations/<version>/recommendation_repository.json`
* `validation/<version>/recommendation_validation.json`
* `priority/<version>/recommendation_priority.json`
* `impact/<version>/recommendation_impact.json`
* `audit/<version>/recommendation_audit.json`

The repository and audit data are append-only. A restart detects an existing immutable version and returns it without rewriting it. The audit records creation, lineage verification, validation, and publication.
