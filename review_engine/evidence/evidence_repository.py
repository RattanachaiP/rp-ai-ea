from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
@dataclass(frozen=True)
class EvidenceWriteResult: created: bool; path: Path; conflict: bool = False
class EvidenceRepository:
 def __init__(self, root: Path | str): self.root = Path(root)
 def save(self, evidence: Mapping[str, object]) -> EvidenceWriteResult:
  evidence_id, trade_id = str(evidence.get("evidence_id", "")), str(evidence.get("trade_id", ""))
  if not evidence_id or not trade_id or any(part in evidence_id + trade_id for part in ("/", "\\", "..")): raise ValueError("INVALID_EVIDENCE_ID_OR_TRADE_ID")
  path = self.root / "evidence" / f"evidence_{evidence_id}.json"; path.parent.mkdir(parents=True, exist_ok=True)
  payload = (json.dumps(evidence, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(); temp = path.with_suffix(".json.tmp")
  if path.exists():
   try:
    if json.loads(path.read_text(encoding="utf-8")).get("evidence_id") == evidence_id: return EvidenceWriteResult(False, path)
   except (OSError, ValueError): pass
   return EvidenceWriteResult(False, path, True)
  try:
   with temp.open("xb") as f: f.write(payload); f.flush(); os.fsync(f.fileno())
   os.link(temp, path); temp.unlink(); return EvidenceWriteResult(True, path)
  except FileExistsError: return EvidenceWriteResult(False, path, True)
  finally:
   if temp.exists(): temp.unlink()
