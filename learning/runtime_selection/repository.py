"""Atomic append-only PR181 repository and snapshot-chain validation."""
import json, os, re, tempfile
from pathlib import Path
from .exceptions import RuntimeKnowledgeSelectionError
from .identity import digest
from .models import RuntimeKnowledgeSelection, RuntimeKnowledgeSelectionSnapshot

_UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

class RuntimeKnowledgeSelectionRepository:
    def __init__(self, root="learning_data/runtime_selection"):
        self.root=Path(root);self.snapshot_root=self.root/"snapshots"
    @staticmethod
    def _bytes(value): return json.dumps(value.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    def _append(self,path,data,collision,prefix):
        path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix=prefix,dir=path.parent);tmp=Path(name)
        try:
            with os.fdopen(fd,"wb") as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
            try: os.link(tmp,path)
            except FileExistsError:
                if path.read_bytes()!=data: raise RuntimeKnowledgeSelectionError(collision) from None
        finally: tmp.unlink(missing_ok=True)
        return path
    def path_for(self,identity):
        if not isinstance(identity,str) or not _UUID.fullmatch(identity): raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_FILENAME")
        return self.root/f"{identity}.json"
    def save(self,value):
        if type(value) is not RuntimeKnowledgeSelection: raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_SELECTION")
        return self._append(self.path_for(value.selection_uuid),self._bytes(value),"SELECTION_COLLISION",".selection-")
    def save_snapshot(self,value):
        if type(value) is not RuntimeKnowledgeSelectionSnapshot: raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_SNAPSHOT")
        return self._append(self.snapshot_root/f"{value.snapshot_uuid}.json",self._bytes(value),"SELECTION_SNAPSHOT_COLLISION",".snapshot-")
    def _load(self,root,model,label,field):
        if not root.exists(): return ()
        output=[]
        for path in sorted(root.glob("*.json")):
            if not _UUID.fullmatch(path.stem): raise RuntimeKnowledgeSelectionError(f"INVALID_{label}_FILENAME")
            try: item=model(**json.loads(path.read_text()))
            except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc: raise RuntimeKnowledgeSelectionError(f"CORRUPT_{label}_REPOSITORY") from exc
            if getattr(item,field)!=path.stem: raise RuntimeKnowledgeSelectionError(f"{label}_FILENAME_IDENTITY_MISMATCH")
            output.append(item)
        return tuple(output)
    def selections(self): return self._load(self.root,RuntimeKnowledgeSelection,"SELECTION","selection_uuid")
    def snapshots(self): return self._load(self.snapshot_root,RuntimeKnowledgeSelectionSnapshot,"SELECTION_SNAPSHOT","snapshot_uuid")
    def identities(self): return tuple((x.selection_uuid,x.selection_digest) for x in self.selections())
    def digest(self): return digest([list(x) for x in self.identities()])
    def latest_snapshot(self):
        snapshots=self.snapshots()
        if not snapshots: return None
        by={x.snapshot_uuid:x for x in snapshots};refs={x.previous_snapshot_uuid for x in snapshots if x.previous_snapshot_uuid};heads=[x for x in snapshots if x.snapshot_uuid not in refs]
        if len(by)!=len(snapshots) or len(heads)!=1: raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
        head=cur=heads[0];seen=set();partition=(head.selection_policy_uuid,head.selection_policy_digest,head.selection_policy_version,head.selector_version)
        while True:
            if cur.snapshot_uuid in seen or (cur.selection_policy_uuid,cur.selection_policy_digest,cur.selection_policy_version,cur.selector_version)!=partition: raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
            seen.add(cur.snapshot_uuid)
            if not cur.previous_snapshot_uuid: break
            previous=by.get(cur.previous_snapshot_uuid)
            if previous is None or previous.snapshot_digest!=cur.previous_snapshot_digest: raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
            cur=previous
        if len(seen)!=len(snapshots): raise RuntimeKnowledgeSelectionError("BROKEN_SELECTION_SNAPSHOT_CHAIN")
        if head.selection_identities!=self.identities(): raise RuntimeKnowledgeSelectionError("SELECTION_SNAPSHOT_MISMATCH")
        if head.repository_digest!=self.digest(): raise RuntimeKnowledgeSelectionError("SELECTION_REPOSITORY_MISMATCH")
        return head
