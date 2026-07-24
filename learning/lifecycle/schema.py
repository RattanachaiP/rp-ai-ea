"""Schema constants for the isolated Knowledge Lifecycle Framework."""
from __future__ import annotations

LIFECYCLE_SCHEMA_VERSION = "1.0"
INITIAL_STATE = "DRAFT"
LIFECYCLE_STATES = frozenset({"DRAFT", "VERIFIED", "ACTIVE", "SUPERSEDED", "RETIRED", "ARCHIVED"})
ALLOWED_TRANSITIONS = {
    "DRAFT": frozenset({"VERIFIED", "ARCHIVED"}),
    "VERIFIED": frozenset({"ACTIVE", "ARCHIVED"}),
    "ACTIVE": frozenset({"SUPERSEDED", "RETIRED"}),
    "SUPERSEDED": frozenset({"ARCHIVED"}),
    "RETIRED": frozenset({"ARCHIVED"}),
    "ARCHIVED": frozenset(),
}
