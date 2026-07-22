import hashlib, json, os
from pathlib import Path
from typing import Mapping
from review_engine.validation import validate_snapshot
class SnapshotConflictError(FileExistsError): pass
class SnapshotRepository:
    """Append-only immutable snapshot store; no canonical trading files are touched."""
    def __init__(self, root): self.root=Path(root)
    def _path(self, snapshot):
        day=snapshot["timeline"]["closed_at_utc"][:10].replace("-", "/")
        return self.root / "snapshots" / day / f"trade_{snapshot['trade_identity']['trade_id']}.json"
    def store(self, snapshot: Mapping):
        snapshot=dict(snapshot); validate_snapshot(snapshot); path=self._path(snapshot); path.parent.mkdir(parents=True,exist_ok=True)
        content=json.dumps(snapshot, sort_keys=True, indent=2)+"\n"
        if path.exists():
            if path.read_text(encoding="utf-8") == content: return {"status":"idempotent", "path":path}
            raise SnapshotConflictError(f"immutable snapshot conflict: {path}")
        temporary=path.with_suffix(".json.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as f: f.write(content); f.flush(); os.fsync(f.fileno())
            os.replace(temporary,path)
        finally:
            if temporary.exists(): temporary.unlink()
        return {"status":"created", "path":path}
