from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from .candidate import CandidatePattern
from .storage import PatternStorage
from .validator import PatternValidator
class PatternRepository:
    def __init__(self, root: str | Path = "learning_data"): self.storage = PatternStorage(root); self.validator = PatternValidator()
    def save(self, pattern: CandidatePattern) -> Path:
        existing = self.storage.all(); self.validator.validate(pattern, existing)
        # An identical deterministic pattern is a successful idempotent append.
        for item in existing:
            if item.pattern_uuid == pattern.pattern_uuid:
                if item.to_dict() == pattern.to_dict(): return self.storage.path_for(pattern.pattern_uuid)
                raise FileExistsError("PATTERN_IMMUTABLE")
        return self.storage.write(pattern)
    def load_pattern(self, pattern_uuid: str) -> CandidatePattern: return self.storage.read(pattern_uuid)
    def query_patterns(self, *, status: str | None = None, conditions: Mapping[str, object] | None = None) -> list[CandidatePattern]:
        found = self.storage.all()
        if status is not None: found = [item for item in found if item.status == status]
        if conditions is not None: found = [item for item in found if all(item.conditions.get(key) == value for key, value in conditions.items())]
        return found
