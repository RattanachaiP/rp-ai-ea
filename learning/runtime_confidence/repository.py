"""Atomic append-only PR182 confidence repository."""
import json, os, re, tempfile
from pathlib import Path
from .exceptions import RuntimeConfidenceError
from .identity import digest
from .models import ConfidenceRecord, ConfidenceSnapshot, PARTITION_FIELDS
_UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

class RuntimeConfidenceRepository:
    def __init__(self, root="learning_data/runtime_confidence"):
        self.root=Path(root); self.snapshot_root=self.root/"snapshots"
    @staticmethod
    def _bytes(v): return json.dumps(v.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    def _append(self,path,data,collision,prefix):
        path.parent.mkdir(parents=True,exist_ok=True); fd,name=tempfile.mkstemp(prefix=prefix,dir=path.parent); tmp=Path(name)
        try:
            with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            try: os.link(tmp,path)
            except FileExistsError:
                if path.read_bytes()!=data: raise RuntimeConfidenceError(collision) from None
        finally: tmp.unlink(missing_ok=True)
        return path
    def path_for(self,i):
        if not isinstance(i,str) or not _UUID.fullmatch(i): raise RuntimeConfidenceError("INVALID_CONFIDENCE_FILENAME")
        return self.root/f"{i}.json"
    def save(self,v):
        if type(v) is not ConfidenceRecord: raise RuntimeConfidenceError("INVALID_CONFIDENCE_RECORD")
        return self._append(self.path_for(v.confidence_uuid),self._bytes(v),"REPLAY_COLLISION",".confidence-")
    def save_snapshot(self,v):
        if type(v) is not ConfidenceSnapshot: raise RuntimeConfidenceError("INVALID_CONFIDENCE_SNAPSHOT")
        return self._append(self.snapshot_root/f"{v.snapshot_uuid}.json",self._bytes(v),"REPLAY_COLLISION",".snapshot-")
    def _load(self,root,model,label,field):
        if not root.exists(): return ()
        out=[]
        for p in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(p.stem): raise RuntimeConfidenceError(f"INVALID_{label}_FILENAME")
            try: item=model(**json.loads(p.read_text()))
            except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc: raise RuntimeConfidenceError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item,field)!=p.stem: raise RuntimeConfidenceError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            out.append(item)
        return tuple(out)
    def records(self): return self._load(self.root,ConfidenceRecord,"CONFIDENCE","confidence_uuid")
    def snapshots(self): return self._load(self.snapshot_root,ConfidenceSnapshot,"CONFIDENCE_SNAPSHOT","snapshot_uuid")
    def identities(self): return tuple((x.confidence_uuid,x.confidence_digest) for x in self.records())
    def digest(self): return digest([list(x) for x in self.identities()])
    def validate_partition(self,expected):
        records=self.records(); snapshots=self.snapshots(); wanted=tuple(expected[n] for n in PARTITION_FIELDS)
        if any(tuple(getattr(x,n) for n in PARTITION_FIELDS)!=wanted for x in (*records,*snapshots)): raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        return records,self.latest_snapshot() if snapshots else None
    def latest_snapshot(self):
        ss=self.snapshots()
        if not ss:return None
        by={x.snapshot_uuid:x for x in ss}; refs={x.previous_snapshot_uuid for x in ss if x.previous_snapshot_uuid}; heads=[x for x in ss if x.snapshot_uuid not in refs]
        if len(by)!=len(ss) or len(heads)!=1: raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        head=cur=heads[0]; seen=set()
        while cur:
            if cur.snapshot_uuid in seen: raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
            seen.add(cur.snapshot_uuid)
            if not cur.previous_snapshot_uuid: break
            prior=by.get(cur.previous_snapshot_uuid)
            if prior is None or prior.snapshot_digest!=cur.previous_snapshot_digest: raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
            cur=prior
        if len(seen)!=len(ss) or head.confidence_identities!=self.identities(): raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
        if head.repository_digest!=self.digest(): raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        return head
