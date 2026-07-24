# PR157 — Active Knowledge Registry

`learning.active_registry.ActiveKnowledgeRegistry` is the canonical, append-only
catalog for Knowledge that has already completed promotion. It accepts caller-
supplied committed Promotion Records and approved Promotion Decisions, and
fails closed when either artifact, their UUID binding, or semantic lineage is
missing or inconsistent. It does not import Promotion Authority, lifecycle,
qualification, analytics, governance, runtime, executor, bridge, MT5, or broker
code; registration is a catalog operation only and never performs promotion.

Entries are immutable `ActiveKnowledgeEntry` events stored atomically at
`learning_data/active_registry/entry_<uuid>.json`. The event projection is
deterministic. Active entries are indexed through read operations by semantic
identity first and knowledge UUID second; `list_active()`, `get_active()`, and
`lookup()` expose ACTIVE only by default. `history()` exposes immutable
append-only history and `get_by_uuid()` permits inspection of terminal state.

Supersession appends a `SUPERSEDED` event for the prior knowledge containing
both the prior activation reference and replacement knowledge UUID, then appends
the replacement `ACTIVE` event. Retirement and archival append terminal events;
they never delete or rewrite activation files. A second active knowledge for a
semantic identity is rejected unless it explicitly supersedes the existing
active knowledge with matching semantic identity.
