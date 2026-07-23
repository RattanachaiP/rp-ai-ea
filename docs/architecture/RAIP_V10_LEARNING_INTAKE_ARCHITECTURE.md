# RAIP V10 — Learning Intake Domain

V10 is an offline, read-only, asynchronous qualification domain. It consumes immutable V6 governance, V7 executive, and V9 validation artefacts and writes only qualification artefacts below `learning_intake/`. It never trains, changes weights or thresholds, modifies runtime payloads or decisions, deploys, or influences trading.

The explicit, versioned `learning_intake_policy.json` is evaluated before publication (Rule #025). Rule #024 permits only governance-approved, executive-finalized, simulation-validated, schema-compatible, lineage-complete, non-duplicate candidates to be `QUALIFIED`.

Publication is atomic (`.tmp`, flush/fsync, rename). Per-candidate reports and registry records are write-once; the registry index is reconstructed atomically. The candidate identity is SHA-256 canonical serialization of `evidence_hash`, `validation_report_id`, `lineage_hash`, `policy_version`, and `schema_version`.
