"""Atomic append-only storage for policy evaluation reports."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from .models import PolicyEvaluationReport
class PolicyEvaluationStorage:
    def __init__(self, root="learning_data"): self.root = Path(root) / "policy"; self.root.mkdir(parents=True, exist_ok=True)
    def path_for(self, evaluation_uuid: str) -> Path:
        if not evaluation_uuid.isalnum(): raise ValueError("INVALID_EVALUATION_UUID")
        return self.root / f"evaluation_{evaluation_uuid}.json"
    def write(self, report: PolicyEvaluationReport) -> Path:
        path, data = self.path_for(report.evaluation_uuid), json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if path.exists():
            if path.read_text(encoding="utf-8") == data: return path
            raise FileExistsError("POLICY_EVALUATION_IMMUTABLE")
        fd, name = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp"); temp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try: os.link(temp, path)
            except FileExistsError:
                if path.read_text(encoding="utf-8") == data: return path
                raise FileExistsError("POLICY_EVALUATION_IMMUTABLE")
            return path
        finally: temp.unlink(missing_ok=True)
    def all(self):
        reports=[]
        for path in sorted(self.root.glob("evaluation_*.json")):
            reports.append(PolicyEvaluationReport(**json.loads(path.read_text(encoding="utf-8"))))
        return tuple(reports)
