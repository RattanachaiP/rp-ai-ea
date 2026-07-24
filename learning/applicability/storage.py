"""Append-only report persistence owned by the Applicability Engine."""
from pathlib import Path
import os
import json
from uuid import uuid4
from dataclasses import asdict
class ApplicabilityReportRepository:
 def __init__(self, root="learning_data"): self.root=Path(root)
 def append(self, report):
  path=self.root/"applicability_reports"/f"report_{report.report_uuid}.json"; data=(json.dumps(asdict(report),sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode(); path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():
   if path.read_bytes()!=data: raise FileExistsError("APPLICABILITY_REPORT_APPEND_ONLY")
   return path
  tmp=path.with_name(f".{path.name}.{uuid4().hex}.tmp")
  try:
   with tmp.open("xb") as f: f.write(data); f.flush()
   try: os.link(tmp, path)
   except FileExistsError: pass
  finally: tmp.unlink(missing_ok=True)
  return path
