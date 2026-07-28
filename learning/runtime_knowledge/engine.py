"""PR180 verifies PR179 evidence and prepares advisory packages only."""
from dataclasses import replace
from learning.common.immutable import thaw
from learning.knowledge_registry import KnowledgeRegistryError,KnowledgeRegistryReport,KnowledgeRegistryRepository,KnowledgeRegistrySnapshot,RegistryRecord
from learning.knowledge_registry.identity import digest as registry_digest,registry_report_uuid
from .exceptions import RuntimeKnowledgeError
from .models import PACKAGE_REASONS,PACKAGE_STATE,PARTITION_FIELDS,RuntimeKnowledgePackage,RuntimeKnowledgePackagingReport,RuntimeKnowledgeSnapshot
from .policy import RuntimeKnowledgePackagingPolicy
from .repository import RuntimeKnowledgeRepository

class RuntimeKnowledgeGate:
 runtime_engine_version="PR180.2.0"
 def __init__(self,registry_repository=None,repository=None,policy=None,*,runtime_engine_version=None):
  self.registry_repository=registry_repository or KnowledgeRegistryRepository();self.repository=repository or RuntimeKnowledgeRepository();self.policy=policy or RuntimeKnowledgePackagingPolicy();self.runtime_engine_version=runtime_engine_version or type(self).runtime_engine_version
  if type(self.registry_repository) is not KnowledgeRegistryRepository:raise RuntimeKnowledgeError("INVALID_REGISTRY")
  if type(self.repository) is not RuntimeKnowledgeRepository:raise RuntimeKnowledgeError("INVALID_RUNTIME_REPOSITORY")
  if type(self.policy) is not RuntimeKnowledgePackagingPolicy:raise RuntimeKnowledgeError("INVALID_RUNTIME_PACKAGING_POLICY")
  if not isinstance(self.runtime_engine_version,str) or not self.runtime_engine_version:raise RuntimeKnowledgeError("RUNTIME_ENGINE_VERSION_MISMATCH")
 def prepare_advisory_package(self,source):
  if type(source) not in (KnowledgeRegistryReport,KnowledgeRegistrySnapshot,RegistryRecord):raise RuntimeKnowledgeError("INVALID_REGISTRY")
  records,source_fields,snapshot,generated=self._verify_source(source);partition=self._partition(records[0]);self._verify_policy(partition)
  if any(tuple(self._partition(x)[n] for n in PARTITION_FIELDS[4:])!=tuple(partition[n] for n in PARTITION_FIELDS[4:]) for x in records):raise RuntimeKnowledgeError("BROKEN_REGISTRY_REPORT_PARTITION")
  existing,previous=self.repository.validate_partition(partition);by_registry={x.source_registry_uuid:x for x in existing};packages=[];new=duplicates=0
  for record in records:
   package=self._package(record,partition,generated);prior=by_registry.get(record.registry_uuid)
   if prior:
    if prior!=package:raise RuntimeKnowledgeError("RUNTIME_PACKAGE_REPLAY_COLLISION")
    package=prior;duplicates+=1
   else:self.repository.save(package);by_registry[record.registry_uuid]=package;new+=1
   packages.append(package)
  identities=self.repository.identities();repo_digest=self.repository.digest();snapshot_values={**partition,"source_registry_snapshot_uuid":snapshot.snapshot_uuid,"source_registry_snapshot_digest":snapshot.snapshot_digest,"source_registry_repository_digest":snapshot.repository_digest,"package_identities":identities,"package_count":len(identities),"repository_digest":repo_digest}
  reusable=previous is not None and all(getattr(previous,k)==v for k,v in snapshot_values.items())
  if reusable:runtime_snapshot=previous
  else:
   runtime_snapshot=RuntimeKnowledgeSnapshot.create(**snapshot_values,previous_snapshot_uuid=previous.snapshot_uuid if previous else None,previous_snapshot_digest=previous.snapshot_digest if previous else None,generated_at=generated,advisory_only=True);self.repository.save_snapshot(runtime_snapshot)
  return RuntimeKnowledgePackagingReport.create(**source_fields,**partition,source_registry_snapshot_uuid=snapshot.snapshot_uuid,source_registry_snapshot_digest=snapshot.snapshot_digest,source_registry_repository_digest=snapshot.repository_digest,runtime_packages=tuple(packages),processed_record_count=len(packages),new_package_count=new,duplicate_package_count=duplicates,advisory_package_prepared_count=len(packages),repository_digest=repo_digest,snapshot_uuid=runtime_snapshot.snapshot_uuid,snapshot_digest=runtime_snapshot.snapshot_digest,generated_at=generated,advisory_only=True)
 run=prepare_advisory_package
 def _verify_source(self,source):
  try:latest=self.registry_repository.latest_snapshot();stored=self.registry_repository.records();snapshots=self.registry_repository.snapshots()
  except KnowledgeRegistryError as exc:raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE") from exc
  if latest is None:raise RuntimeKnowledgeError("INVALID_REGISTRY")
  by={x.registry_uuid:x for x in stored};snap_by={x.snapshot_uuid:x for x in snapshots}
  if type(source) is KnowledgeRegistryReport:
   try:clean=replace(source)
   except (TypeError,ValueError) as exc:raise RuntimeKnowledgeError("BROKEN_REGISTRY_REPORT") from exc
   if registry_report_uuid(clean.identity_payload())!=clean.report_uuid:raise RuntimeKnowledgeError("BROKEN_REGISTRY_REPORT")
   snapshot=snap_by.get(clean.snapshot_uuid)
   if snapshot is None or snapshot.snapshot_digest!=clean.snapshot_digest:raise RuntimeKnowledgeError("REGISTRY_REPORT_SNAPSHOT_MISMATCH")
   if snapshot.repository_digest!=clean.repository_digest:raise RuntimeKnowledgeError("REGISTRY_REPORT_REPOSITORY_MISMATCH")
   records=clean.registry_records;identities=set(snapshot.record_identities)
   if any((x.registry_uuid,x.registry_digest) not in identities for x in records):raise RuntimeKnowledgeError("REGISTRY_REPORT_RECORD_SET_MISMATCH")
   source_fields=dict(source_artifact_type="KNOWLEDGE_REGISTRY_REPORT",source_registry_report_uuid=clean.report_uuid,source_registry_report_digest=registry_digest(clean.to_dict()),source_registry_uuid=None,source_registry_digest=None);generated=clean.generated_at
  elif type(source) is KnowledgeRegistrySnapshot:
   snapshot=snap_by.get(source.snapshot_uuid)
   if snapshot is None or snapshot!=source:raise RuntimeKnowledgeError("REGISTRY_REPORT_SNAPSHOT_MISMATCH")
   records=[]
   for identity,content_digest in snapshot.record_identities:
    record=by.get(identity)
    if record is None or record.registry_digest!=content_digest:raise RuntimeKnowledgeError("REGISTRY_REPORT_RECORD_SET_MISMATCH")
    records.append(record)
   if not records:raise RuntimeKnowledgeError("INVALID_REGISTRY")
   source_fields=dict(source_artifact_type="KNOWLEDGE_REGISTRY_SNAPSHOT",source_registry_report_uuid=None,source_registry_report_digest=None,source_registry_uuid=None,source_registry_digest=None);generated=snapshot.generated_at
  else:
   try:clean=replace(source)
   except (TypeError,ValueError) as exc:raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE") from exc
   pair=(clean.registry_uuid,clean.registry_digest);ordered=self._ordered_snapshots(snapshots);matches=[x for x in ordered if pair in x.record_identities]
   if not matches:raise RuntimeKnowledgeError("REGISTRY_RECORD_SNAPSHOT_MEMBERSHIP_MISSING")
   snapshot=matches[0];records=(clean,);source_fields=dict(source_artifact_type="KNOWLEDGE_REGISTRY_RECORD",source_registry_report_uuid=None,source_registry_report_digest=None,source_registry_uuid=clean.registry_uuid,source_registry_digest=clean.registry_digest);generated=clean.recorded_at
  for record in records:
   prior=by.get(record.registry_uuid)
   if prior is None or prior!=record:raise RuntimeKnowledgeError("REGISTRY_REPORT_RECORD_SET_MISMATCH" if type(source) is KnowledgeRegistryReport else "REGISTRY_DIGEST_MISMATCH")
   if record.registry_state!=self.policy.required_registry_state or record.advisory_only is not self.policy.required_advisory_only:raise RuntimeKnowledgeError("INVALID_REGISTRY")
  return tuple(records),source_fields,snapshot,generated
 @staticmethod
 def _ordered_snapshots(snapshots):
  by={x.snapshot_uuid:x for x in snapshots};children={x.previous_snapshot_uuid:x for x in snapshots if x.previous_snapshot_uuid};roots=[x for x in snapshots if x.previous_snapshot_uuid is None]
  if len(roots)!=1:raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE")
  out=[];cur=roots[0]
  while cur:out.append(cur);cur=children.get(cur.snapshot_uuid)
  if len(out)!=len(by):raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE")
  return out
 def _partition(self,r):return dict(runtime_engine_version=self.runtime_engine_version,runtime_packaging_policy_uuid=self.policy.runtime_packaging_policy_uuid,runtime_packaging_policy_digest=self.policy.runtime_packaging_policy_digest,runtime_packaging_policy_version=self.policy.runtime_packaging_policy_version,source_registry_engine_version=r.registry_engine_version,source_registry_admission_policy_uuid=r.registry_admission_policy_uuid,source_registry_admission_policy_digest=r.registry_admission_policy_digest,source_registry_admission_policy_version=r.registry_admission_policy_version,source_promotion_engine_version=r.source_promotion_engine_version,source_promotion_policy_uuid=r.source_promotion_policy_uuid,source_promotion_policy_digest=r.source_promotion_policy_digest,source_promotion_policy_version=r.source_promotion_policy_version)
 def _verify_policy(self,p):
  checks=((self.policy.required_registry_engine_version,p["source_registry_engine_version"]),(self.policy.required_registry_admission_policy_version,p["source_registry_admission_policy_version"]),(self.policy.required_promotion_engine_version,p["source_promotion_engine_version"]),(self.policy.required_promotion_policy_version,p["source_promotion_policy_version"]))
  if any(required is not None and required!=actual for required,actual in checks):raise RuntimeKnowledgeError("RUNTIME_PACKAGING_POLICY_MISMATCH")
 @staticmethod
 def _package(record,partition,generated):
  special={"source_registry_uuid":record.registry_uuid,"source_registry_digest":record.registry_digest,"source_registry_state":record.registry_state,"source_registry_reasons":record.registry_reasons,"source_registry_recorded_at":record.recorded_at}
  provenance={name:thaw(getattr(record,name)) for name in record.__dataclass_fields__ if (name.startswith("source_") or name in ("replay_digest","evidence_envelope_uuid","evidence_envelope_digest","knowledge_uuid","knowledge_version","mining_config_digest","outcome_contract","memory_version","memory_state","promotion_policy_thresholds","threshold_monotonicity_result")) and name not in partition}
  return RuntimeKnowledgePackage.create(**partition,**provenance,**special,runtime_package_state=PACKAGE_STATE,runtime_package_reasons=PACKAGE_REASONS,generated_at=generated,advisory_only=True)
