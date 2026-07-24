# PR157 — Active Knowledge Registry

`learning.active_registry.ActiveKnowledgeRegistry` is the canonical append-only
read model for Knowledge lifecycle state. It performs no promotion, supersession,
retirement, archival, qualification, or governance decision.

The registry accepts only authoritative receipts whose UUID and canonical content
digest are present in an injected trust registry. Receipts are bound to an approved
source authority, monotonic sequence, authoritative timestamp, semantic identity,
source event UUID, configuration version, and lineage reference. Arbitrary caller
Promotion dictionaries are not executable registry inputs.

## Event model

- `ACTIVATION`: trusted Promotion Authority receipt; exposes one ACTIVE Knowledge.
- `SUPERSESSION`: one atomic receipt containing prior and replacement identities;
  projection changes old to SUPERSEDED and new to ACTIVE without a two-file crash window.
- `RETIREMENT`: trusted Lifecycle Authority receipt; changes ACTIVE to RETIRED.
- `ARCHIVAL`: trusted Lifecycle Authority receipt; changes RETIRED to ARCHIVED.

Registry entries are immutable files at
`learning_data/active_registry/entry_<event_uuid>.json`. Replay ordering uses the
trusted monotonic sequence, never caller-selected timestamps or file ordering.
Corrupted records and duplicate sequences fail closed and block reads and writes.

Semantic identity locks use exclusive filesystem ownership, lease expiration,
host/PID metadata, stale-lock recovery, and owner verification before release.
This prevents concurrent registration of multiple ACTIVE entries for one semantic
identity.

The public write boundary is deliberately limited to `register(receipt)` for
ACTIVATION/SUPERSESSION and `apply_lifecycle_event(receipt)` for
RETIREMENT/ARCHIVAL. Runtime consumers use `get_active()`, `resolve()`,
`list_active()`, `lookup()`, and `history()` as read-only projections.
