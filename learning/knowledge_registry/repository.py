"""Atomic append-only PR179 repository with complete partition and chain checks."""
import json,os,re,tempfile
from pathlib import Path
from .exceptions import KnowledgeRegistryError
from .identity import digest
from .models import KnowledgeRegistrySnapshot,RegistryRecord
_UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PARTITION_FIELDS=("registry_engine_version","registry_admission_policy_uuid","registry_admission_policy_digest","registry_admission_policy_version","source_promotion_engine_version","source_promotion_policy_uuid","source_promotion_policy_digest","source_promotion_policy_version")
ERRORS=("REGISTRY_ENGINE_VERSION_MISMATCH","REGISTRY_ADMISSION_POLICY_UUID_MISMATCH","REGISTRY_ADMISSION_POLICY_DIGEST_MISMATCH","REGISTRY_ADMISSION_POLICY_VERSION_MISMATCH","PROMOTION_ENGINE_IDENTITY_MISMATCH","PROMOTION_POLICY_UUID_MISMATCH","PROMOTION_POLICY_DIGEST_MISMATCH","PROMOTION_POLICY_VERSION_MISMATCH")
class KnowledgeRegistryRepository:
 def __init__(self,root="learning_data/knowledge_registry"): self.root=Path(root);self.snapshot_root=self.root/"snapshots"
 @staticmethod
 def _bytes(v): return json.dumps(v.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False).encode()
 def _append(self,path,data,collision,prefix):
  path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix=prefix,dir=path.parent);tmp=Path(name)
  try:
   with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
   try:os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise KnowledgeRegistryError(collision) from None
  finally:tmp.unlink(missing_ok=True)
  return path
 def path_for(self,i):
  if not isinstance(i,str) or not _UUID.fullmatch(i):raise KnowledgeRegistryError("INVALID_REGISTRY_FILENAME")
  return self.root/f"{i}.json"
 def save(self,r):
  if type(r) is not RegistryRecord:raise KnowledgeRegistryError("INVALID_REGISTRY_RECORD")
  return self._append(self.path_for(r.registry_uuid),self._bytes(r),"REGISTRY_COLLISION",".registry-")
 def save_snapshot(self,s):
  if type(s) is not KnowledgeRegistrySnapshot:raise KnowledgeRegistryError("INVALID_REGISTRY_SNAPSHOT")
  return self._append(self.snapshot_root/f"{s.snapshot_uuid}.json",self._bytes(s),"REGISTRY_SNAPSHOT_COLLISION",".snapshot-")
 def _load(self,root,model,label,field):
  if not root.exists():return ()
  out=[]
  for p in sorted(root.glob("*.json")):
   if not _UUID.fullmatch(p.stem):raise KnowledgeRegistryError(f"INVALID_{label}_FILENAME")
   try:x=model(**json.loads(p.read_text()))
   except (OSError,ValueError,TypeError,json.JSONDecodeError) as e:raise KnowledgeRegistryError(f"CORRUPT_{label}_REPOSITORY") from e
   if getattr(x,field)!=p.stem:raise KnowledgeRegistryError(f"{label}_FILENAME_IDENTITY_MISMATCH")
   out.append(x)
  return tuple(out)
 def records(self):return self._load(self.root,RegistryRecord,"REGISTRY","registry_uuid")
 def snapshots(self):return self._load(self.snapshot_root,KnowledgeRegistrySnapshot,"REGISTRY_SNAPSHOT","snapshot_uuid")
 def identities(self):return tuple((x.registry_uuid,x.registry_digest) for x in self.records())
 def digest(self):return digest([list(x) for x in self.identities()])
 def validate_partition(self,expected):
  records=self.records();snapshots=self.snapshots()
  for item in (*records,*snapshots):
   for field,error in zip(PARTITION_FIELDS,ERRORS):
    if getattr(item,field)!=expected[field]:raise KnowledgeRegistryError(error)
  latest=self.latest_snapshot() if snapshots else None
  return records,latest
 def latest_snapshot(self):
  ss=self.snapshots()
  if not ss:return None
  by={x.snapshot_uuid:x for x in ss};refs={x.previous_snapshot_uuid for x in ss if x.previous_snapshot_uuid};heads=[x for x in ss if x.snapshot_uuid not in refs]
  if len(by)!=len(ss) or len(heads)!=1:raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
  head=cur=heads[0];seen=set();partition=tuple(getattr(head,x) for x in PARTITION_FIELDS)
  while True:
   if cur.snapshot_uuid in seen:raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
   seen.add(cur.snapshot_uuid)
   if tuple(getattr(cur,x) for x in PARTITION_FIELDS)!=partition:raise KnowledgeRegistryError("MIXED_REGISTRY_PARTITION")
   if cur.record_count!=len(cur.record_identities):raise KnowledgeRegistryError("REGISTRY_SNAPSHOT_RECORD_COUNT_MISMATCH")
   if not cur.previous_snapshot_uuid:break
   prev=by.get(cur.previous_snapshot_uuid)
   if prev is None or prev.snapshot_digest!=cur.previous_snapshot_digest:raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
   cur=prev
  if len(seen)!=len(ss):raise KnowledgeRegistryError("BROKEN_REGISTRY_SNAPSHOT_CHAIN")
  if head.record_identities!=self.identities() or head.repository_digest!=self.digest():raise KnowledgeRegistryError("REGISTRY_SNAPSHOT_INTEGRITY_FAILURE")
  return head
