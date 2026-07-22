"""Append-only, atomically-published Insight repository."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Mapping

class InsightRepository:
    def __init__(self, root: Path | str): self.root = Path(root)
    def save(self, report: Mapping[str, object]) -> Path:
        version = str(report.get("insight_version", ""))
        if len(version) != 64 or any(c not in "0123456789abcdef" for c in version): raise ValueError("INVALID_INSIGHT_VERSION")
        record = {"insight_id": version, **dict(report)}
        path = self.root / "insights" / version / "insight_repository.json"
        self._write_once(path, record)
        self._write_once(self.root / "executive" / version / "insight_report.json", dict(report))
        self._write_once(self.root / "reports" / version / "insight_report.json", dict(report))
        self._write_once(self.root / "ranking" / version / "ranking.json", dict(report.get("metrics", {})))
        return path
    @staticmethod
    def _write_once(path: Path, document: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): return
        payload = json.dumps(document, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            # The existence guard makes publication append-only; rename makes a completed
            # JSON file appear atomically (readers never observe a partial document).
            if not path.exists(): os.rename(tmp, path)
        except FileExistsError: pass
        finally:
            if tmp.exists(): tmp.unlink()
