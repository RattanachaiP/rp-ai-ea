"""Schema constants for the immutable verified-knowledge repository."""
from __future__ import annotations

KNOWLEDGE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"
KNOWLEDGE_STATUSES = frozenset({"ACTIVE", "DEPRECATED", "SUPERSEDED", "ARCHIVED"})
REQUIRED_FIELDS = (
    "knowledge_uuid", "knowledge_version", "pattern_uuid", "validation_uuid",
    "created_timestamp", "applicable_symbols", "applicable_sessions",
    "applicable_market_states", "sample_count", "verified_win_rate", "average_rr",
    "confidence_placeholder", "knowledge_status",
)
