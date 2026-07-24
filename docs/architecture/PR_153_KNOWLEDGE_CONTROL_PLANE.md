# PR153 — Knowledge Control Plane

## Authority boundary

`learning.control_plane.KnowledgeControlPlane` is a read-only coordination
surface. It observes published Knowledge Repository, Governance, Lifecycle,
Analytics, and optional Policy outputs. It does not own storage and has no
methods for promotion, retirement, policy execution, lifecycle mutation, or
runtime interaction.

The control plane must not be imported by the Decision Engine, executor,
broker, or MT5 code. Consumers use it only for inspection and future
promotion-preparation workflows.

## Public API

The API is intentionally limited to these read operations:

- `get_knowledge(uuid)`
- `get_status()`
- `get_snapshot([uuid])`
- `get_health()`
- `get_lineage(uuid)`
- `get_policy_result([uuid])`
- `get_governance(uuid)`
- `get_lifecycle(uuid)`
- `get_analytics()`

`capabilities()` reports this interface for discovery. Policy is injected as a
read-only provider; if it is not installed, its health is `UNKNOWN` rather
than failing or creating policy state.

## Snapshot and failure behavior

Snapshots canonicalize mapping keys and collection order and include a digest
of the canonical observation. Each snapshot carries governance, lifecycle,
analytics, policy evaluation, lineage, repository version, schema versions,
and configuration versions.

Subsystem exceptions are isolated. They are surfaced in `get_health()` as
`FAILED` (or `DEGRADED` for a missing individual record); the control plane
does not retry, repair, mutate, or substitute data.
