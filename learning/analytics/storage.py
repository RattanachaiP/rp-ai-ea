from __future__ import annotations
import json, os, tempfile
from pathlib import Path
class AnalyticsStorage:
 def __init__(self, root="learning_data"): self.root=Path(root)/"analytics"; self.root.mkdir(parents=True,exist_ok=True)
 def path_for(self, uuid): return self.root/f"report_{uuid}.json"
 def write(self, report):
  path=self.path_for(report.analytics_uuid); data=json.dumps(report.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
  if path.exists():
   existing=json.loads(path.read_text())
   # Replaying an identical immutable source/configuration is idempotent; the
   # generation timestamp is audit metadata, not an alternate artifact.
   if (existing.get("knowledge_snapshot", {}).get("source_digest") == report.knowledge_snapshot["source_digest"]
       and existing.get("analytics_version") == report.analytics_version
       and existing.get("configuration_version") == report.configuration_version): return path
   raise FileExistsError("ANALYTICS_IMMUTABLE")
  fd,tmp=tempfile.mkstemp(dir=self.root,prefix=".report_");
  try:
   with os.fdopen(fd,"w",encoding="utf-8") as f: f.write(data); f.flush(); os.fsync(f.fileno())
   os.link(tmp,path); os.unlink(tmp)
  except FileExistsError: os.unlink(tmp); raise
  return path
