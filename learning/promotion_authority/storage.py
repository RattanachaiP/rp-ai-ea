"""Atomic append-only persistence for immutable promotion records."""
from __future__ import annotations
import json, os
from pathlib import Path
from uuid import UUID, uuid4
from .models import PromotionRecord
class PromotionRecordStorage:
    def __init__(self, root="learning_data"): self.root = Path(root)
    @property
    def directory(self): return self.root / "promotion_records"
    def path_for(self, record_uuid):
        try: canonical = str(UUID(record_uuid))
        except (ValueError, TypeError, AttributeError) as exc: raise ValueError("INVALID_PROMOTION_RECORD_UUID") from exc
        return self.directory / f"record_{canonical}.json"
    def write(self, record: PromotionRecord):
        path=self.path_for(record.record_uuid); path.parent.mkdir(parents=True, exist_ok=True)
        data=(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
        if path.exists():
            if path.read_bytes()==data: return path
            raise FileExistsError("PROMOTION_RECORD_IMMUTABLE")
        tmp=path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp,path)
            except FileExistsError as exc:
                if path.exists() and path.read_bytes()==data: return path
                raise FileExistsError("PROMOTION_RECORD_IMMUTABLE") from exc
        finally: tmp.unlink(missing_ok=True)
        return path
    def discard_uncommitted(self, record: PromotionRecord):
        """Remove only a record whose enclosing transaction did not commit."""
        self.path_for(record.record_uuid).unlink(missing_ok=True)
    def all(self):
        records=[]
        if not self.directory.exists(): return ()
        for path in sorted(self.directory.glob("record_*.json")):
            try: records.append(PromotionRecord(**json.loads(path.read_text())))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError): continue
        return tuple(sorted(records, key=lambda r:(r.timestamp,r.record_uuid)))
