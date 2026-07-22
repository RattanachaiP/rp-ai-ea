from __future__ import annotations
from dataclasses import dataclass
import json, os
from pathlib import Path
from typing import Mapping
from review_engine.validation.schema_validator import validate_snapshot
@dataclass(frozen=True)
class SnapshotWriteResult: created: bool; path: Path; conflict: bool=False
class SnapshotRepository:
 def __init__(self, root:Path|str): self.root=Path(root)
 def save(self,snapshot:Mapping[str,object])->SnapshotWriteResult:
  validate_snapshot(snapshot); identity=snapshot["trade_identity"]; trade_id=identity["trade_id"]; created=snapshot["created_at_utc"][:10].split("-")
  if any(part in str(trade_id) for part in ("/","\\","..")): raise ValueError("INVALID_TRADE_ID")
  path=self.root/"snapshots"/created[0]/created[1]/created[2]/f"trade_{trade_id}.json"; path.parent.mkdir(parents=True,exist_ok=True)
  serialized=(json.dumps(snapshot,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
  if path.exists():
   try:
    existing=json.loads(path.read_text(encoding="utf-8"))
    if (existing.get("trade_identity",{}).get("trade_id") == trade_id and existing.get("provenance",{}).get("source_event_ids") == snapshot.get("provenance",{}).get("source_event_ids")):
     return SnapshotWriteResult(False,path)
   except (OSError, ValueError, TypeError): pass
   return SnapshotWriteResult(False,path,True)
  temp=path.with_suffix(".json.tmp")
  try:
   with temp.open("xb") as stream: stream.write(serialized);stream.flush();os.fsync(stream.fileno())
   os.link(temp,path); temp.unlink(); return SnapshotWriteResult(True,path)
  except FileExistsError: return SnapshotWriteResult(False,path,True)
  finally:
   if temp.exists(): temp.unlink()
