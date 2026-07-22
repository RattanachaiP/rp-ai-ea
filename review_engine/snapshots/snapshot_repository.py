import hashlib, json, os
from pathlib import Path
from ..validation.schema_validator import canonical_sha256, validate_snapshot
class SnapshotRepository:
    def __init__(self, root): self.root = Path(root)
    def store(self, snapshot):
        validate_snapshot(snapshot); identity = snapshot["trade_identity"]; closed = snapshot["timeline"]["closed_at_utc"]
        path = self.root / "snapshots" / closed[:10].replace("-", "/") / ("trade_" + self._safe_id(identity["trade_id"]) + ".json")
        payload = dict(snapshot); payload["provenance"] = dict(payload["provenance"]); payload["provenance"]["snapshot_sha256"] = ""
        payload["provenance"]["snapshot_sha256"] = canonical_sha256(payload)
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        if path.exists():
            existing = path.read_bytes()
            current = json.loads(existing)
            def evidence(value):
                value = dict(value)
                value.pop("snapshot_id", None); value.pop("created_at_utc", None); value.pop("provenance", None)
                return canonical_sha256(value)
            if existing == data or evidence(current) == evidence(payload):
                return {"created": False, "idempotent": True, "path": path, "snapshot": current}
            return {"created": False, "idempotent": False, "conflict": True, "path": path}
        path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(temp, "xb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(temp, path)
        finally:
            if temp.exists(): temp.unlink()
        return {"created": True, "idempotent": False, "path": path, "snapshot": payload}
    @staticmethod
    def _safe_id(value):
        return hashlib.sha256(str(value).encode()).hexdigest()[:24]
    def read_for_date(self, date_utc):
        directory = self.root / "snapshots" / date_utc.replace("-", "/")
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("trade_*.json"))] if directory.exists() else []
