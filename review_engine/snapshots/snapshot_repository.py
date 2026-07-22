import json, os
from datetime import datetime, timezone
from pathlib import Path
class SnapshotRepository:
    def __init__(self, root): self.root=Path(root)
    def store(self, snapshot):
        closed=datetime.fromisoformat(snapshot["timeline"]["closed_at_utc"].replace("Z","+00:00")).astimezone(timezone.utc)
        path=self.root/"snapshots"/f"{closed:%Y/%m/%d}"/f"trade_{snapshot['trade_identity']['trade_id']}.json"; path.parent.mkdir(parents=True,exist_ok=True)
        content=json.dumps(snapshot,sort_keys=True,separators=(",",":"))
        if path.exists():
            existing=path.read_text(encoding="utf-8")
            if existing == content: return {"created":False,"idempotent":True,"path":str(path)}
            return {"created":False,"conflict":True,"path":str(path)}
        tmp=path.with_suffix(path.suffix+".tmp")
        try:
            with tmp.open("x",encoding="utf-8") as f: f.write(content); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path); return {"created":True,"path":str(path)}
        finally:
            if tmp.exists(): tmp.unlink()
    def for_date(self, date_utc):
        directory=self.root/"snapshots"/date_utc.replace("-","/")
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("trade_*.json"))] if directory.exists() else []
