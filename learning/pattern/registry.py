"""Read-only status and schema registry for pattern consumers."""
from .schema import PATTERN_VERSION, SCHEMA_VERSION, STATUSES
class PatternRegistry:
    pattern_version = PATTERN_VERSION
    schema_version = SCHEMA_VERSION
    statuses = tuple(sorted(STATUSES))
