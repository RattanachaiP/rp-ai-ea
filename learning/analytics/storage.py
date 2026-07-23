"""Portable append-only storage using exclusive creation (Windows compatible)."""
from __future__ import annotations
import json
import os
from pathlib import Path
class AnalyticsStorage:
    def __init__(self, root="learning_data"): self.root = Path(root) / "analytics"; self.root.mkdir(parents=True, exist_ok=True)
    def path_for(self, analytics_uuid): return self.root / f"report_{analytics_uuid}.json"
    def write(self, report):
        path = self.path_for(report.analytics_uuid); data = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if path.read_text(encoding="utf-8") == data: return path
            raise FileExistsError("ANALYTICS_IMMUTABLE")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path
