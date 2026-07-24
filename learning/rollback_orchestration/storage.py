"""Canonical JSON, atomic and append-only PR169 evidence storage."""
from __future__ import annotations
import json, os
from pathlib import Path
from uuid import uuid4

class RollbackStorage:
    def __init__(self, root="learning_data"): self.root = Path(root) / "rollback_orchestration"
    def write(self, section, name, value):
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        data = (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        path = self.root / section / f"{name}.json"; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() == data: return path
            raise FileExistsError("ROLLBACK_APPEND_ONLY")
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp, path)
            except FileExistsError: raise FileExistsError("ROLLBACK_APPEND_ONLY")
        finally: tmp.unlink(missing_ok=True)
        return path
