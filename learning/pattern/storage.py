"""Atomic append-only JSON persistence for patterns."""
from __future__ import annotations
import json, os
from pathlib import Path
from .candidate import CandidatePattern
class PatternStorage:
    def __init__(self, root: str | Path = "learning_data"): self.root = Path(root)
    @property
    def directory(self) -> Path: return self.root / "patterns"
    def path_for(self, pattern_uuid: str) -> Path:
        if not pattern_uuid or any(part in pattern_uuid for part in ("/", "\\", "..")): raise ValueError("INVALID_PATTERN_UUID")
        return self.directory / f"pattern_{pattern_uuid}.json"
    def write(self, pattern: CandidatePattern) -> Path:
        path = self.path_for(pattern.pattern_uuid); path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            prior = self.read(pattern.pattern_uuid)
            if prior.to_dict() == pattern.to_dict(): return path
            raise FileExistsError("PATTERN_IMMUTABLE")
        payload = (json.dumps(pattern.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("xb") as handle: handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, path)
        except FileExistsError: raise FileExistsError("PATTERN_IMMUTABLE")
        finally:
            if temporary.exists(): temporary.unlink()
        return path
    def read(self, pattern_uuid: str) -> CandidatePattern:
        with self.path_for(pattern_uuid).open(encoding="utf-8") as handle: return CandidatePattern.from_dict(json.load(handle))
    def all(self) -> list[CandidatePattern]:
        if not self.directory.exists(): return []
        return [CandidatePattern.from_dict(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.directory.glob("pattern_*.json"))]
