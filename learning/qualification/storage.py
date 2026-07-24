"""Atomic append-only persistence for qualification reports."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from uuid import UUID
from .models import QualificationReport

class QualificationStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "qualification"; self.root.mkdir(parents=True, exist_ok=True)
    def path_for(self, qualification_uuid: str) -> Path:
        try: canonical = str(UUID(qualification_uuid))
        except (ValueError, AttributeError) as exc: raise ValueError("INVALID_QUALIFICATION_UUID") from exc
        if canonical != qualification_uuid.lower(): raise ValueError("INVALID_QUALIFICATION_UUID")
        return self.root / f"qualification_{canonical}.json"
    def write(self, report: QualificationReport) -> Path:
        path, data = self.path_for(report.qualification_uuid), json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if path.exists():
            if path.read_text(encoding="utf-8") == data: return path
            raise FileExistsError("QUALIFICATION_REPORT_IMMUTABLE")
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp")
        temp = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try: os.link(temp, path)
            except FileExistsError as exc: raise FileExistsError("QUALIFICATION_REPORT_IMMUTABLE") from exc
            if os.name != "nt":
                descriptor = os.open(self.root, os.O_RDONLY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
            return path
        finally: temp.unlink(missing_ok=True)
