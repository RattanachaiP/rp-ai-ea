"""Append-only persistence for validation audit records and verified knowledge."""
from __future__ import annotations
import json, os
from pathlib import Path
from .schema import ValidationResult
from .verifier import VerifiedKnowledge

class ValidationRepository:
    def __init__(self, root: str | Path = "learning_data"): self.root = Path(root)
    @property
    def audit_directory(self) -> Path: return self.root / "validation_results"
    @property
    def verified_directory(self) -> Path: return self.root / "verified_patterns"
    def _append(self, directory: Path, name: str, payload: dict[str, object]) -> Path:
        directory.mkdir(parents=True, exist_ok=True); path = directory / name
        data = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(); temporary = path.with_suffix(path.suffix + ".tmp")
        if path.exists():
            if path.read_bytes() == data: return path
            raise FileExistsError("VALIDATION_IMMUTABLE")
        try:
            with temporary.open("xb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, path)
        finally:
            if temporary.exists(): temporary.unlink()
        return path
    def save_result(self, result: ValidationResult) -> Path:
        return self._append(self.audit_directory, f"validation_{result.pattern_uuid}.json", result.to_dict())
    def save_knowledge(self, knowledge: VerifiedKnowledge) -> Path:
        return self._append(self.verified_directory, f"verified_{knowledge.pattern_uuid}.json", knowledge.to_dict())
