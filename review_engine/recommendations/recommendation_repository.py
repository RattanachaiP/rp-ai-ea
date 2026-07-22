"""Append-only atomic storage for validated passive recommendation packages."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Mapping

class RecommendationRepository:
    def __init__(self, root: Path | str): self.root = Path(root)
    def existing_ids(self):
        result = set()
        for path in self.root.glob("recommendations/*/recommendation_repository.json"):
            try: result.update(str(row.get("recommendation_id")) for row in json.loads(path.read_text()).get("recommendations", []))
            except (OSError, json.JSONDecodeError, AttributeError): continue
        return result
    def save(self, package: Mapping[str, object], validation: Mapping[str, object]) -> Path:
        version = str(package.get("recommendation_version", ""))
        if len(version) != 64: raise ValueError("INVALID_RECOMMENDATION_VERSION")
        published = dict(package) | {"recommendations": [dict(row) | {"validation_status": "VALID"} for row in package["recommendations"]]}
        path = self.root / "recommendations" / version / "recommendation_repository.json"
        self._write_once(path, published)
        base = {key: published[key] for key in ("schema_version", "producer", "owner", "created_at", "insight_version", "recommendation_version", "lineage_hash")}
        self._write_once(self.root / "validation" / version / "recommendation_validation.json", base | dict(validation))
        self._write_once(self.root / "priority" / version / "recommendation_priority.json", base | {"recommendations": [{"recommendation_id": r["recommendation_id"], "priority": r["priority"]} for r in published["recommendations"]]})
        self._write_once(self.root / "impact" / version / "recommendation_impact.json", base | {"recommendations": [{"recommendation_id": r["recommendation_id"], "estimated_impact": r["estimated_impact"]} for r in published["recommendations"]]})
        audit = base | {"events": [{"event": event, "recommendation_ids": [r["recommendation_id"] for r in published["recommendations"]]} for event in ("creation", "lineage_verification", "validation", "publication")]}
        self._write_once(self.root / "audit" / version / "recommendation_audit.json", audit)
        return path
    @staticmethod
    def _write_once(path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): return
        tmp = path.with_suffix(path.suffix + ".tmp"); payload = json.dumps(document, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
        try:
            with tmp.open("xb") as handle: handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            if not path.exists(): os.rename(tmp, path)
        except FileExistsError: pass
        finally:
            if tmp.exists(): tmp.unlink()
