"""Schema constants for passive verified-knowledge governance records."""
from __future__ import annotations

GOVERNANCE_SCHEMA_VERSION = "1.0"
LIFECYCLE_STATES = frozenset({"DRAFT", "VERIFIED", "ACTIVE", "SUPERSEDED", "RETIRED", "ARCHIVED"})
TERMINAL_LIFECYCLE_STATES = frozenset({"RETIRED", "ARCHIVED"})
ALLOWED_TRANSITIONS = {
    "DRAFT": frozenset({"DRAFT", "VERIFIED", "ARCHIVED"}),
    "VERIFIED": frozenset({"VERIFIED", "ACTIVE", "ARCHIVED"}),
    "ACTIVE": frozenset({"ACTIVE", "SUPERSEDED", "RETIRED", "ARCHIVED"}),
    "SUPERSEDED": frozenset({"SUPERSEDED", "RETIRED", "ARCHIVED"}),
    "RETIRED": frozenset({"RETIRED", "ARCHIVED"}),
    "ARCHIVED": frozenset({"ARCHIVED"}),
}
