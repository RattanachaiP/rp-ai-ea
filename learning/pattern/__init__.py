"""Candidate-only historical pattern discovery API."""
from .candidate import CandidatePattern
from .discovery import PatternDiscovery, discover, discover_incremental
from .repository import PatternRepository
from .validator import PatternValidator, PatternValidationError

def load_pattern(pattern_uuid: str, *, repository: PatternRepository | None = None) -> CandidatePattern:
    return (repository or PatternRepository()).load_pattern(pattern_uuid)
def query_patterns(*, repository: PatternRepository | None = None, **filters: object) -> list[CandidatePattern]:
    return (repository or PatternRepository()).query_patterns(**filters) # type: ignore[arg-type]
__all__ = ["CandidatePattern", "PatternDiscovery", "PatternRepository", "PatternValidator", "PatternValidationError", "discover", "discover_incremental", "load_pattern", "query_patterns"]
