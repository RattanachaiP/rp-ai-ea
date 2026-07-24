"""Atomic, immutable, append-only storage for promotion decision reports."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from uuid import UUID
from .models import PromotionDecisionReport

class PromotionDecisionStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "promotion_decision"; self.root.mkdir(parents=True, exist_ok=True)
    def path_for(self, decision_uuid: str) -> Path:
        try: canonical = str(UUID(decision_uuid))
        except (ValueError, AttributeError) as exc: raise ValueError("INVALID_PROMOTION_DECISION_UUID") from exc
        if canonical != decision_uuid.lower(): raise ValueError("INVALID_PROMOTION_DECISION_UUID")
        return self.root / f"decision_{canonical}.json"
    def write(self, report: PromotionDecisionReport) -> Path:
        path = self.path_for(report.decision_uuid); data = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if path.exists():
            if path.read_text(encoding="utf-8") == data: return path
            raise FileExistsError("PROMOTION_DECISION_REPORT_IMMUTABLE")
        fd, name = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp"); temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try: os.link(temporary, path)
            except FileExistsError as exc: raise FileExistsError("PROMOTION_DECISION_REPORT_IMMUTABLE") from exc
            return path
        finally: temporary.unlink(missing_ok=True)
