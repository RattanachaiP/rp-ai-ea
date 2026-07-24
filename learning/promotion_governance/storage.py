"""Canonical JSON, atomic, append-only promotion history storage."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from .models import PromotionAudit
class PromotionHistoryStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "promotion_history"; self.root.mkdir(parents=True, exist_ok=True)
    def write(self, audit: PromotionAudit) -> Path:
        path=self.root / f"promotion_{audit.promotion_uuid}.json"; data=json.dumps(audit.to_dict(), sort_keys=True,separators=(",",":"),allow_nan=False)
        if path.exists():
            if path.read_text(encoding="utf-8") == data: return path
            raise FileExistsError("PROMOTION_HISTORY_APPEND_ONLY")
        fd,tmp=tempfile.mkstemp(dir=self.root,prefix=".promotion_",suffix=".tmp")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as h: h.write(data); h.flush(); os.fsync(h.fileno())
            try: os.link(tmp,path)
            except FileExistsError as e: raise FileExistsError("PROMOTION_HISTORY_APPEND_ONLY") from e
            return path
        finally: Path(tmp).unlink(missing_ok=True)
    def all(self):
        return tuple(PromotionAudit(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.root.glob("promotion_*.json")))
