"""Canonical, serialisable schema for offline candidate patterns."""
from __future__ import annotations

PATTERN_VERSION = "1.0"
SCHEMA_VERSION = "1.0"
REQUIRED_STATISTICS = (
    "samples", "wins", "losses", "breakeven", "win_rate", "avg_profit",
    "avg_loss", "avg_rr", "avg_mae", "avg_mfe", "avg_holding",
    "median_profit", "median_loss", "stddev_profit",
)
STATUSES = frozenset({"NEW", "INSUFFICIENT_DATA", "CANDIDATE", "ARCHIVED", "REJECTED"})
