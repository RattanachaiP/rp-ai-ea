"""Atomic append-only PR180 repository with complete partition checks."""
import json,os,re,tempfile
from pathlib import Path
from .exceptions import RuntimeKnowledgeError
from .identity import digest
from .models import PARTITION_FIELDS,RuntimeKnowledgePackage,RuntimeKnowledgeSnapshot
_UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ERRORS=("RUNTIME_ENGINE_VERSION_MISMATCH","RUNTIME_PACKAGING_POLICY_UUID_MISMATCH","RUNTIME_PACKAGING_POLICY_DIGEST_MISMATCH","RUNTIME_PACKAGING_POLICY_VERSION_MISMATCH","SOURCE_REGISTRY_ENGINE_VERSION_MISMATCH","SOURCE_REGISTRY_ADMISSION_POLICY_UUID_MISMATCH","SOURCE_REGISTRY_ADMISSION_POLICY_DIGEST_MISMATCH","SOURCE_REGISTRY_ADMISSION_POLICY_VERSION_MISMATCH","SOURCE_PROMOTION_ENGINE_VERSION_MISMATCH","SOURCE_PROMOTION_POLICY_UUID_MISMATCH","SOURCE_PROMOTION_POLICY_DIGEST_MISMATCH","SOURCE_PROMOTION_POLICY_VERSION_MISMATCH")
class RuntimeKnowledgeRepository:
 def __init__(self,root="learning_data/runtime_knowledge"):self.root=Path(root);self.snapshot_root=self.root/"snapshots"
 @staticmethod
 def _bytes(v):return json.dumps(v.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False).encode()
 def _append(self,path,data,collision,prefix):
  path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(prefix=prefix,dir=path.parent);tmp=Path(name)
  try:
   with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
   try:os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise RuntimeKnowledgeError(collision) from None
  finally:tmp.unlink(missing_ok=True)
  return path
 def path_for(self,i):
  if not isinstance(i,str) or not _UUID.fullmatch(i):raise RuntimeKnowledgeError("INVALID_RUNTIME_PACKAGE_FILENAME")
  return self.root/f"{i}.json"
 def save(self,v):
  if type(v) is not RuntimeKnowledgePackage:raise RuntimeKnowledgeError("INVALID_RUNTIME_KNOWLEDGE_PACKAGE")
  return self._append(self.path_for(v.runtime_package_uuid),self._bytes(v),"RUNTIME_PACKAGE_COLLISION",".package-")
 def save_snapshot(self,v):
  if type(v) is not RuntimeKnowledgeSnapshot:raise RuntimeKnowledgeError("INVALID_RUNTIME_KNOWLEDGE_SNAPSHOT")
  return self._append(self.snapshot_root/f"{v.snapshot_uuid}.json",self._bytes(v),"RUNTIME_SNAPSHOT_COLLISION",".snapshot-")
 def _load(self,root,model,label,field):
  if not root.exists():return ()
  out=[]
  for path in sorted(root.glob("*.json")):
   if not _UUID.fullmatch(path.stem):raise RuntimeKnowledgeError(f"INVALID_{label}_FILENAME")
   try:item=model(**json.loads(path.read_text()))
   except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:raise RuntimeKnowledgeError(f"CORRUPT_{label}_REPOSITORY") from exc
   if getattr(item,field)!=path.stem:raise RuntimeKnowledgeError(f"{label}_FILENAME_IDENTITY_MISMATCH")
   out.append(item)
  return tuple(out)
 def packages(self):return self._load(self.root,RuntimeKnowledgePackage,"RUNTIME_PACKAGE","runtime_package_uuid")
 def snapshots(self):return self._load(self.snapshot_root,RuntimeKnowledgeSnapshot,"RUNTIME_SNAPSHOT","snapshot_uuid")
 def identities(self):return tuple((x.runtime_package_uuid,x.runtime_package_digest) for x in self.packages())
 def digest(self):return digest([list(x) for x in self.identities()])
 def validate_partition(self,expected):
  packages=self.packages();snapshots=self.snapshots()
  partitions={tuple(getattr(x,n) for n in PARTITION_FIELDS) for x in (*packages,*snapshots)}
  if len(partitions)>1:raise RuntimeKnowledgeError("MIXED_RUNTIME_KNOWLEDGE_PARTITION")
  for item in (*packages,*snapshots):
   for name,error in zip(PARTITION_FIELDS,ERRORS):
    if getattr(item,name)!=expected[name]:raise RuntimeKnowledgeError(error)
  return packages,self.latest_snapshot() if snapshots else None
 def latest_snapshot(self):
  ss=self.snapshots()
  if not ss:return None
  by={x.snapshot_uuid:x for x in ss};refs={x.previous_snapshot_uuid for x in ss if x.previous_snapshot_uuid};heads=[x for x in ss if x.snapshot_uuid not in refs]
  if len(by)!=len(ss) or len(heads)!=1:raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
  head=cur=heads[0];seen=set();partition=tuple(getattr(head,n) for n in PARTITION_FIELDS)
  while True:
   if cur.snapshot_uuid in seen:raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
   seen.add(cur.snapshot_uuid)
   if tuple(getattr(cur,n) for n in PARTITION_FIELDS)!=partition:raise RuntimeKnowledgeError("MIXED_RUNTIME_KNOWLEDGE_PARTITION")
   if cur.package_count!=len(cur.package_identities):raise RuntimeKnowledgeError("RUNTIME_SNAPSHOT_PACKAGE_COUNT_MISMATCH")
   if not cur.previous_snapshot_uuid:break
   previous=by.get(cur.previous_snapshot_uuid)
   if previous is None or previous.snapshot_digest!=cur.previous_snapshot_digest:raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
   cur=previous
  if len(seen)!=len(ss):raise RuntimeKnowledgeError("BROKEN_RUNTIME_SNAPSHOT_CHAIN")
  if head.package_identities!=self.identities():raise RuntimeKnowledgeError("RUNTIME_SNAPSHOT_PACKAGE_IDENTITY_MISMATCH")
  if head.repository_digest!=self.digest():raise RuntimeKnowledgeError("RUNTIME_SNAPSHOT_REPOSITORY_MISMATCH")
  return head
