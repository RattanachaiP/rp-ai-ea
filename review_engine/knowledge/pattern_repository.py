"""Append-only pattern repository with fsync plus atomic publication."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


class PatternRepository:
    def __init__(self, root: Path | str): self.root = Path(root)
    def save(self, report: Mapping[str, object]) -> Path:
        version = str(report.get("pattern_repository_version", ""))
        if len(version) != 64 or any(char not in "0123456789abcdef" for char in version): raise ValueError("INVALID_PATTERN_REPOSITORY_VERSION")
        path = self.root / "patterns" / version / "pattern_repository.json"
        self._write_once(path, self._repository_document(report))
        self._write_once(self.root / "statistics" / version / "pattern_statistics.json", report)
        self._write_once(self.root / "knowledge" / version / "knowledge.json", report)
        return path
    @staticmethod
    def _write_once(path: Path, document: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): return
        payload = json.dumps(document, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
        temporary = path.with_suffix(".json.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, path)
        except FileExistsError:
            pass
        finally:
            if temporary.exists(): temporary.unlink()
    @staticmethod
    def _repository_document(report):
        patterns = report.get("statistics", {}).get("pattern_statistics", {}) if isinstance(report.get("statistics"), Mapping) else {}
        records = []
        for classification in sorted(patterns):
            stats = patterns[classification] if isinstance(patterns[classification], Mapping) else {}
            records.append({"pattern_id": f"{report['pattern_repository_version']}:{classification}", "classification": classification, "sample_size": stats.get("trade_count", 0), "win_rate": stats.get("win_rate"), "profit_factor": PatternRepository._profit_factor(stats), "average_rr": stats.get("average_rr"), "confidence": stats.get("average_confidence"), "created_at": report.get("created_at"), "schema_version": report.get("schema_version"), "owner": report.get("owner")})
        return {key: report[key] for key in ("schema_version", "producer", "owner", "created_at", "source_schema_version", "generated_from", "pattern_repository_version")} | {"patterns": records}
    @staticmethod
    def _profit_factor(stats):
        profit, loss = stats.get("average_profit"), stats.get("average_loss")
        try: return round(float(profit) / abs(float(loss)), 6) if profit is not None and loss not in (None, 0) else None
        except (TypeError, ValueError): return None
