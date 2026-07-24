"""Deterministic, append-only PR163 report persistence."""
from __future__ import annotations
from hashlib import sha256
import json, os
from pathlib import Path
from uuid import uuid4
from .models import LearningDailyReport, LearningWeeklyReport, LearningCandidate

class LearningReportRepository:
    def __init__(self, root: str | Path = "learning_reports") -> None: self.root=Path(root)
    @staticmethod
    def _bytes(value): return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
    def _append(self, relative: str, value: dict) -> Path:
        path=self.root/relative; data=self._bytes(value); path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes()!=data: raise FileExistsError("LEARNING_REPORT_APPEND_ONLY")
            return path
        temp=path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temp.open("xb") as fh: fh.write(data); fh.flush(); os.fsync(fh.fileno())
            try: os.link(temp,path)
            except FileExistsError:
                if path.read_bytes()!=data: raise FileExistsError("LEARNING_REPORT_APPEND_ONLY")
        finally: temp.unlink(missing_ok=True)
        return path
    def append_daily(self, report: LearningDailyReport) -> Path:
        return self._append(f"daily/{report.report_date}.json", report.to_dict())
    def append_weekly(self, report: LearningWeeklyReport) -> Path:
        return self._append(f"weekly/{report.week_start}.json", report.to_dict())
    def append_dashboard(self, statistics, recommendations, daily_reports=()) -> tuple[Path,Path,Path]:
        # Dashboard snapshots are immutable content-addressed data, never replacement files.
        payloads=(("knowledge_summary", [x.to_dict() for x in statistics]), ("candidate_summary", [LearningCandidate(r.knowledge_uuid,r.semantic_identity,r,next(x for x in statistics if x.knowledge_uuid==r.knowledge_uuid)).to_dict() for r in recommendations]), ("daily_learning", [x.to_dict() for x in daily_reports]))
        paths=[]
        for name,value in payloads:
            digest=sha256(self._bytes(value)).hexdigest()
            paths.append(self._append(f"dashboard/{name}_{digest}.json", value))
        return tuple(paths)
