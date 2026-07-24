"""Atomic, append-only, replay-safe persistence for PR173 attribution reports."""
from __future__ import annotations
from pathlib import Path
import json, os, tempfile
from .models import KnowledgeOutcomeAttributionReport
class KnowledgeOutcomeAttributionRepository:
 def __init__(self,root='learning_data'): self.root=Path(root)/'outcome_attribution';self.root.mkdir(parents=True,exist_ok=True)
 def path_for(self,attribution_uuid): return self.root/f'report_{attribution_uuid}.json'
 def save(self,report):
  data=json.dumps(report.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False).encode(); path=self.path_for(report.attribution_uuid)
  if path.exists():
   if path.read_bytes()==data:return path
   raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
  fd,tmp=tempfile.mkstemp(prefix='.report_',suffix='.tmp',dir=self.root)
  try:
   with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   try: os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise FileExistsError('APPEND_ONLY_REPORT_COLLISION')
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  return path
