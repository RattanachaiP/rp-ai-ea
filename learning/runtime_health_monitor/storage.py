"""Atomic append-only evidence storage for PR171."""
import json, os
from pathlib import Path
from uuid import uuid4
from .models import RuntimeHealthMonitorError
class RuntimeHealthMonitorStorage:
 def __init__(self,root='learning_data'): self.root=Path(root)/'runtime_health_monitor'
 def write(self,section,name,value):
  payload=value.to_dict() if hasattr(value,'to_dict') else value; data=(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode(); path=self.root/section/f'{name}.json'; path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():
   if path.read_bytes()==data:return path
   raise RuntimeHealthMonitorError('RUNTIME_HEALTH_APPEND_ONLY_VIOLATION')
  tmp=path.with_name('.'+path.name+'.'+uuid4().hex+'.tmp')
  try:
   with tmp.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
   try: os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data: raise RuntimeHealthMonitorError('RUNTIME_HEALTH_APPEND_ONLY_VIOLATION')
  finally: tmp.unlink(missing_ok=True)
  return path
