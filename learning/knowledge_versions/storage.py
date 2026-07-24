"""Append-only storage for immutable PR167 version artifacts."""
from __future__ import annotations
import json, os
from pathlib import Path
from uuid import uuid4

class KnowledgeVersionStorage:
    def __init__(self, root="learning_data"): self.root = Path(root) / "knowledge_versions"
    def _write(self, section: str, name: str, payload: dict) -> Path:
        path = self.root / section / name
        data = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() == data: return path
            raise FileExistsError("KNOWLEDGE_VERSION_APPEND_ONLY")
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp, path)
            except FileExistsError:
                if path.exists() and path.read_bytes() == data: return path
                raise FileExistsError("KNOWLEDGE_VERSION_APPEND_ONLY")
        finally: tmp.unlink(missing_ok=True)
        return path
    def write_version(self, value): return self._write("snapshots", f"version_{value.version_uuid}.json", value.to_dict())
    def write_manifest(self, value): return self._write("manifest", f"manifest_{value.version_uuid}.json", value.to_dict())
    def write_lineage(self, value): return self._write("lineage", f"lineage_{value.version_uuid}.json", value.to_dict())
    def write_history(self, value): return self._write("history", f"history_{value['version_uuid']}.json", value)
    def read_all(self):
        from .models import KnowledgeVersion
        directory = self.root / "snapshots"
        if not directory.exists(): return ()
        records=[]
        for path in sorted(directory.glob("version_*.json")):
            try: records.append(KnowledgeVersion(**json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc: raise RuntimeError(f"KNOWLEDGE_VERSION_CORRUPTED:{path.name}") from exc
        return tuple(records)
