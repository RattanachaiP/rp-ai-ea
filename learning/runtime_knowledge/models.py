"""Independently auditable immutable PR180 advisory packaging artifacts."""
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from learning.common.immutable import freeze, thaw
from learning.knowledge_registry import RegistryRecord
from learning.pattern_memory.models import json_safe, valid_digest, valid_timestamp, valid_uuid
from .identity import digest, package_uuid, report_uuid, snapshot_uuid

PACKAGE_STATE = "ADVISORY_PACKAGE_PREPARED"
PACKAGE_REASONS = ("PR179_REGISTRY_ENTRY_VERIFIED", "PR180_PACKAGING_POLICY_PASSED",
                   "ADVISORY_RUNTIME_PACKAGE_PREPARED")
PARTITION_FIELDS = ("runtime_engine_version", "runtime_packaging_policy_uuid",
 "runtime_packaging_policy_digest", "runtime_packaging_policy_version",
 "source_registry_engine_version", "source_registry_admission_policy_uuid",
 "source_registry_admission_policy_digest", "source_registry_admission_policy_version",
 "source_promotion_engine_version", "source_promotion_policy_uuid",
 "source_promotion_policy_digest", "source_promotion_policy_version")

def _text(*values): return all(isinstance(value, str) and value for value in values)
def _finite(value):
    if isinstance(value, Mapping): return all(isinstance(k, str) and _finite(v) for k,v in value.items())
    if isinstance(value, (tuple,list)): return all(_finite(v) for v in value)
    return not isinstance(value, float) or isfinite(value)
def _mapping(value):
    raw=thaw(value); return isinstance(raw,dict) and json_safe(raw) and _finite(raw)

@dataclass(frozen=True)
class RuntimeKnowledgePackage:
    runtime_package_uuid: str
    runtime_package_digest: str
    runtime_engine_version: str
    runtime_packaging_policy_uuid: str
    runtime_packaging_policy_digest: str
    runtime_packaging_policy_version: str
    source_registry_uuid: str
    source_registry_digest: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_uuid: str
    source_promotion_digest: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_validation_uuid: str
    source_validation_digest: str
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    source_memory_uuid: str
    source_memory_digest: str
    source_pattern_uuid: str
    source_pattern_hash: str
    source_report_uuid: str
    source_policy_uuid: str
    source_policy_version: str
    source_attribution_uuid: str
    source_digest: str
    replay_digest: str
    evidence_envelope_uuid: str
    evidence_envelope_digest: str
    knowledge_uuid: str
    knowledge_version: str
    source_engine_version: str
    mining_config_digest: str
    outcome_contract: tuple[str,str]
    memory_version: str
    memory_state: str
    source_validation_state: str
    source_validation_reasons: tuple[str,...]
    source_validation_statistics: Mapping
    source_validated_at: str
    source_validation_thresholds: Mapping
    promotion_policy_thresholds: Mapping
    threshold_monotonicity_result: str
    source_promotion_state: str
    source_promotion_reasons: tuple[str,...]
    source_promotion_created_at: str
    source_registry_state: str
    source_registry_reasons: tuple[str,...]
    source_registry_recorded_at: str
    runtime_package_state: str
    runtime_package_reasons: tuple[str,...]
    generated_at: str
    advisory_only: bool=True

    def __post_init__(self):
        for name in ("outcome_contract","source_validation_reasons","source_promotion_reasons",
                     "source_registry_reasons","runtime_package_reasons"):
            object.__setattr__(self,name,tuple(getattr(self,name)))
        for name in ("source_validation_statistics","source_validation_thresholds","promotion_policy_thresholds"):
            object.__setattr__(self,name,freeze(thaw(getattr(self,name))))
        try: RegistryRecord(**self.registry_record_dict())
        except (TypeError,ValueError) as exc: raise ValueError("INVALID_RUNTIME_PACKAGE_PROVENANCE") from exc
        uuids=(self.runtime_package_uuid,self.runtime_packaging_policy_uuid)
        digests=(self.runtime_package_digest,self.runtime_packaging_policy_digest)
        if (not all(valid_uuid(v) for v in uuids) or not all(valid_digest(v) for v in digests)
            or not _text(*(getattr(self,n) for n in PARTITION_FIELDS if n.endswith("version")))
            or not all(_mapping(getattr(self,n)) for n in ("source_validation_statistics","source_validation_thresholds","promotion_policy_thresholds"))
            or self.runtime_package_state!=PACKAGE_STATE or self.runtime_package_reasons!=PACKAGE_REASONS
            or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or package_uuid(self.identity_payload())!=self.runtime_package_uuid
            or digest(self.digest_payload())!=self.runtime_package_digest): raise ValueError("INVALID_RUNTIME_KNOWLEDGE_PACKAGE")

    def registry_record_dict(self):
        special={"registry_uuid":self.source_registry_uuid,"registry_digest":self.source_registry_digest,
         "registry_engine_version":self.source_registry_engine_version,
         "registry_admission_policy_uuid":self.source_registry_admission_policy_uuid,
         "registry_admission_policy_digest":self.source_registry_admission_policy_digest,
         "registry_admission_policy_version":self.source_registry_admission_policy_version,
         "registry_state":self.source_registry_state,"registry_reasons":list(self.source_registry_reasons),
         "recorded_at":self.source_registry_recorded_at,"advisory_only":True}
        fields=RegistryRecord.__dataclass_fields__
        for name in fields:
            if name in special: continue
            special[name]=thaw(getattr(self,name))
        return special
    def identity_payload(self): return {n:thaw(getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"runtime_package_uuid","runtime_package_digest"}}
    def digest_payload(self): return {"runtime_package_uuid":self.runtime_package_uuid,**self.identity_payload()}
    def to_dict(self): return {"runtime_package_uuid":self.runtime_package_uuid,"runtime_package_digest":self.runtime_package_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**values):
        values={k:thaw(v) for k,v in values.items()}; identity=package_uuid(values)
        return cls(runtime_package_uuid=identity,runtime_package_digest=digest({"runtime_package_uuid":identity,**values}),**values)

@dataclass(frozen=True)
class RuntimeKnowledgeSnapshot:
    snapshot_uuid: str; snapshot_digest: str
    runtime_engine_version: str; runtime_packaging_policy_uuid: str
    runtime_packaging_policy_digest: str; runtime_packaging_policy_version: str
    source_registry_engine_version: str; source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str; source_registry_admission_policy_version: str
    source_promotion_engine_version: str; source_promotion_policy_uuid: str
    source_promotion_policy_digest: str; source_promotion_policy_version: str
    source_registry_snapshot_uuid: str; source_registry_snapshot_digest: str
    source_registry_repository_digest: str
    package_identities: tuple[tuple[str,str],...]; package_count: int; repository_digest: str
    previous_snapshot_uuid: str|None; previous_snapshot_digest: str|None
    generated_at: str; advisory_only: bool=True
    def __post_init__(self):
        ids=tuple(tuple(x) for x in self.package_identities);object.__setattr__(self,"package_identities",ids)
        previous=(self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest))
        if (not all(valid_uuid(getattr(self,n)) for n in ("snapshot_uuid","runtime_packaging_policy_uuid","source_registry_admission_policy_uuid","source_promotion_policy_uuid","source_registry_snapshot_uuid"))
            or not all(valid_digest(getattr(self,n)) for n in ("snapshot_digest","runtime_packaging_policy_digest","source_registry_admission_policy_digest","source_promotion_policy_digest","source_registry_snapshot_digest","source_registry_repository_digest","repository_digest"))
            or not _text(*(getattr(self,n) for n in PARTITION_FIELDS if n.endswith("version"))) or ids!=tuple(sorted(ids)) or self.package_count!=len(ids)
            or len({x[0] for x in ids})!=len(ids) or not all(len(x)==2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in ids)
            or not previous or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload())!=self.snapshot_uuid or digest(self.identity_payload())!=self.snapshot_digest): raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SNAPSHOT")
    def identity_payload(self): return {n:([list(x) for x in self.package_identities] if n=="package_identities" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"snapshot_uuid","snapshot_digest"}}
    def to_dict(self): return {"snapshot_uuid":self.snapshot_uuid,"snapshot_digest":self.snapshot_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**v):
        v["package_identities"]=tuple(sorted(v["package_identities"]));p={**v,"package_identities":[list(x) for x in v["package_identities"]]};return cls(snapshot_uuid=snapshot_uuid(p),snapshot_digest=digest(p),**v)

@dataclass(frozen=True)
class RuntimeKnowledgePackagingReport:
    report_uuid: str; source_artifact_type: str
    source_registry_report_uuid: str|None; source_registry_report_digest: str|None
    source_registry_uuid: str|None; source_registry_digest: str|None
    source_registry_snapshot_uuid: str; source_registry_snapshot_digest: str; source_registry_repository_digest: str
    runtime_engine_version: str; runtime_packaging_policy_uuid: str; runtime_packaging_policy_digest: str; runtime_packaging_policy_version: str
    source_registry_engine_version: str; source_registry_admission_policy_uuid: str; source_registry_admission_policy_digest: str; source_registry_admission_policy_version: str
    source_promotion_engine_version: str; source_promotion_policy_uuid: str; source_promotion_policy_digest: str; source_promotion_policy_version: str
    runtime_packages: tuple[RuntimeKnowledgePackage,...]
    processed_record_count: int; new_package_count: int; duplicate_package_count: int; advisory_package_prepared_count: int
    repository_digest: str; snapshot_uuid: str; snapshot_digest: str; generated_at: str; advisory_only: bool=True
    def __post_init__(self):
        packages=tuple(self.runtime_packages);object.__setattr__(self,"runtime_packages",packages)
        report_source=self.source_artifact_type=="KNOWLEDGE_REGISTRY_REPORT" and valid_uuid(self.source_registry_report_uuid) and valid_digest(self.source_registry_report_digest) and self.source_registry_uuid is None and self.source_registry_digest is None
        record_source=self.source_artifact_type=="KNOWLEDGE_REGISTRY_RECORD" and valid_uuid(self.source_registry_uuid) and valid_digest(self.source_registry_digest) and self.source_registry_report_uuid is None and self.source_registry_report_digest is None
        partition=tuple(getattr(self,n) for n in PARTITION_FIELDS)
        if (not valid_uuid(self.report_uuid) or not(report_source or record_source) or not all(valid_uuid(getattr(self,n)) for n in ("source_registry_snapshot_uuid","runtime_packaging_policy_uuid","source_registry_admission_policy_uuid","source_promotion_policy_uuid","snapshot_uuid"))
            or not all(valid_digest(getattr(self,n)) for n in ("source_registry_snapshot_digest","source_registry_repository_digest","runtime_packaging_policy_digest","source_registry_admission_policy_digest","source_promotion_policy_digest","repository_digest","snapshot_digest"))
            or not all(type(x) is RuntimeKnowledgePackage for x in packages) or any(tuple(getattr(x,n) for n in PARTITION_FIELDS)!=partition for x in packages)
            or self.processed_record_count!=len(packages) or self.new_package_count+self.duplicate_package_count!=len(packages)
            or self.advisory_package_prepared_count!=sum(x.runtime_package_state==PACKAGE_STATE for x in packages)
            or not valid_timestamp(self.generated_at) or self.advisory_only is not True or report_uuid(self.identity_payload())!=self.report_uuid): raise ValueError("INVALID_RUNTIME_KNOWLEDGE_PACKAGING_REPORT")
    def identity_payload(self): return {n:([x.to_dict() for x in self.runtime_packages] if n=="runtime_packages" else getattr(self,n)) for n in self.__dataclass_fields__ if n!="report_uuid"}
    def to_dict(self): return {"report_uuid":self.report_uuid,**self.identity_payload()}
    @classmethod
    def create(cls,**v):
        p={**v,"runtime_packages":[x.to_dict() for x in v["runtime_packages"]]};return cls(report_uuid=report_uuid(p),**v)
