"""Immutable snapshot persistence with idempotent content checks."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any
from ..collector.event_types import canonical_json
class SnapshotConflictError(RuntimeError): pass
class SnapshotRepository:
    def __init__(self, root: Path): self.root = Path(root)
    def store(self, snapshot: dict[str, Any]) -> bool:
        identity = snapshot["trade_identity"]; trade_id = identity["trade_id"]
        if Path(trade_id).name != trade_id: raise ValueError("TRADE_ID_PATH_TRAVERSAL")
        from datetime import datetime
        instant = datetime.fromisoformat(snapshot["timeline"]["closed_at_utc"].replace("Z", "+00:00"))
        target = self.root / "snapshots" / instant.strftime("%Y/%m/%d") / f"trade_{trade_id}.json"
        payload = canonical_json(snapshot)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_text(encoding="utf-8") == payload: return False
            raise SnapshotConflictError("SNAPSHOT_CONFLICT_FOR_TRADE_ID")
        temporary = target.with_suffix(".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists(): temporary.unlink()
        return True
