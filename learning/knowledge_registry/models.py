"""Immutable and independently auditable PR179 governance artifacts."""
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from learning.common.immutable import freeze, thaw
from learning.pattern_memory.models import json_safe, valid_digest, valid_timestamp, valid_uuid
from learning.pattern_promotion.identity import digest as promotion_digest, promotion_policy_uuid
from .identity import digest, registry_report_uuid, registry_snapshot_uuid, registry_uuid
REGISTRY_STATES = ("REJECTED", "NOT_ADMITTED", "ADVISORY_ENTRY_RECORDED")
def _strings(xs): return all(isinstance(x,str) and x for x in xs)
def _finite(v):
    if isinstance(v, Mapping): return all(isinstance(k,str) and _finite(x) for k,x in v.items())
    if isinstance(v,(list,tuple)): return all(_finite(x) for x in v)
    return not isinstance(v,float) or isfinite(v)
def _mapping(v):
    raw=thaw(v); return isinstance(raw,dict) and json_safe(raw) and _finite(raw)

@dataclass(frozen=True)
class RegistryRecord:
    registry_uuid: str
    registry_digest: str
    registry_engine_version: str
    registry_admission_policy_uuid: str
    registry_admission_policy_digest: str
    registry_admission_policy_version: str
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
    outcome_contract: tuple[str, str]
    memory_version: str
    memory_state: str
    source_validation_state: str
    source_validation_reasons: tuple[str, ...]
    source_validation_statistics: Mapping
    source_validated_at: str
    source_validation_thresholds: Mapping
    promotion_policy_thresholds: Mapping
    threshold_monotonicity_result: str
    source_promotion_state: str
    source_promotion_reasons: tuple[str, ...]
    source_promotion_created_at: str
    registry_state: str
    registry_reasons: tuple[str, ...]
    recorded_at: str
    advisory_only: bool = True
    def __post_init__(self):
        for n in ("outcome_contract","source_validation_reasons","source_promotion_reasons","registry_reasons"): object.__setattr__(self,n,tuple(getattr(self,n)))
        for n in ("source_validation_statistics","source_validation_thresholds","promotion_policy_thresholds"): object.__setattr__(self,n,freeze(thaw(getattr(self,n))))
        uuids=(self.registry_uuid,self.registry_admission_policy_uuid,self.source_promotion_uuid,self.source_promotion_policy_uuid,self.source_validation_uuid,self.source_memory_uuid,self.source_pattern_uuid,self.source_report_uuid,self.source_policy_uuid,self.source_attribution_uuid,self.evidence_envelope_uuid,self.knowledge_uuid)
        digests=(self.registry_digest,self.registry_admission_policy_digest,self.source_promotion_digest,self.source_promotion_policy_digest,self.source_validation_digest,self.source_validation_config_digest,self.source_memory_digest,self.source_pattern_hash,self.source_digest,self.replay_digest,self.evidence_envelope_digest,self.mining_config_digest)
        versions=(self.registry_engine_version,self.registry_admission_policy_version,self.source_promotion_engine_version,self.source_promotion_policy_version,self.source_validator_version,self.source_validation_policy_version,self.source_policy_version,self.knowledge_version,self.source_engine_version,self.memory_version)
        source_thresholds=thaw(self.source_validation_thresholds); promotion_thresholds=thaw(self.promotion_policy_thresholds)
        policy_payload={"promotion_policy_version":self.source_promotion_policy_version,
            **promotion_thresholds,"required_validation_state":"STATISTICALLY_CONSISTENT"}
        reason_binding=((self.source_promotion_state=="POLICY_CRITERIA_MET" and "IMMUTABLE_PROMOTION_POLICY_CRITERIA_MET" in self.source_promotion_reasons)
            or (self.source_promotion_state=="INSUFFICIENT_PROMOTION_EVIDENCE" and any("INSUFFICIENT" in x or "NOT_MET" in x for x in self.source_promotion_reasons))
            or (self.source_promotion_state=="REJECTED" and any("REJECTED" in x for x in self.source_promotion_reasons)))
        registry_binding=((self.registry_state=="ADVISORY_ENTRY_RECORDED" and self.registry_reasons==("PR178_POLICY_CRITERIA_CONFIRMED","PR179_ADMISSION_POLICY_PASSED","ADVISORY_GOVERNANCE_ENTRY_RECORDED"))
            or (self.registry_state=="NOT_ADMITTED" and self.registry_reasons in (("PR178_PROMOTION_EVIDENCE_INSUFFICIENT","PR179_ADMISSION_NOT_RECORDED"),("PR179_ADMISSION_POLICY_NOT_SATISFIED","PR179_ADMISSION_NOT_RECORDED")))
            or (self.registry_state=="REJECTED" and self.registry_reasons==("PR178_PROMOTION_REJECTED","PR179_ADMISSION_REJECTED")))
        if (not all(valid_uuid(x) for x in uuids) or not all(valid_digest(x) for x in digests) or not _strings(versions)
            or len(self.outcome_contract)!=2 or not _strings(self.outcome_contract) or self.memory_state!="STORED"
            or self.source_validation_state not in ("INVALID","INSUFFICIENT_EVIDENCE","STATISTICALLY_CONSISTENT")
            or self.threshold_monotonicity_result!="PASSED" or self.source_promotion_state not in ("REJECTED","INSUFFICIENT_PROMOTION_EVIDENCE","POLICY_CRITERIA_MET")
            or not all(_strings(getattr(self,n)) for n in ("source_validation_reasons","source_promotion_reasons","registry_reasons"))
            or not all(_mapping(getattr(self,n)) for n in ("source_validation_statistics","source_validation_thresholds","promotion_policy_thresholds"))
            or set(source_thresholds)!={"minimum_sample_count","minimum_support","minimum_confidence","minimum_expectancy"}
            or set(promotion_thresholds)!=set(source_thresholds)
            or promotion_digest(source_thresholds)!=self.source_validation_config_digest
            or promotion_policy_uuid(policy_payload)!=self.source_promotion_policy_uuid
            or promotion_digest(policy_payload)!=self.source_promotion_policy_digest
            or any(promotion_thresholds[k]<source_thresholds[k] for k in source_thresholds)
            or not reason_binding or not registry_binding
            or self.registry_state not in REGISTRY_STATES or not valid_timestamp(self.source_validated_at) or not valid_timestamp(self.source_promotion_created_at) or not valid_timestamp(self.recorded_at)
            or self.advisory_only is not True or registry_uuid(self.identity_payload())!=self.registry_uuid or digest(self.digest_payload())!=self.registry_digest): raise ValueError("INVALID_REGISTRY_RECORD")
    def identity_payload(self): return {n:thaw(getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"registry_uuid","registry_digest"}}
    def digest_payload(self): return {"registry_uuid":self.registry_uuid,**self.identity_payload()}
    def to_dict(self): return {"registry_uuid":self.registry_uuid,"registry_digest":self.registry_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**v):
        v={k:thaw(x) for k,x in v.items()}; i=registry_uuid(v); return cls(registry_uuid=i,registry_digest=digest({"registry_uuid":i,**v}),**v)

@dataclass(frozen=True)
class KnowledgeRegistrySnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    registry_engine_version: str
    registry_admission_policy_uuid: str
    registry_admission_policy_digest: str
    registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    record_identities: tuple[tuple[str,str],...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str|None
    previous_snapshot_digest: str|None
    generated_at: str
    advisory_only: bool=True
    def __post_init__(self):
        p=tuple(tuple(x) for x in self.record_identities); object.__setattr__(self,"record_identities",p)
        if (not all(valid_uuid(x) for x in (self.snapshot_uuid,self.registry_admission_policy_uuid,self.source_promotion_policy_uuid)) or not all(valid_digest(x) for x in (self.snapshot_digest,self.registry_admission_policy_digest,self.source_promotion_policy_digest,self.repository_digest)) or not _strings((self.registry_engine_version,self.registry_admission_policy_version,self.source_promotion_engine_version,self.source_promotion_policy_version)) or p!=tuple(sorted(p)) or self.record_count!=len(p) or len({x[0] for x in p})!=len(p) or not all(len(x)==2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in p) or (self.previous_snapshot_uuid is None)!=(self.previous_snapshot_digest is None) or (self.previous_snapshot_uuid is not None and not valid_uuid(self.previous_snapshot_uuid)) or (self.previous_snapshot_digest is not None and not valid_digest(self.previous_snapshot_digest)) or not valid_timestamp(self.generated_at) or self.advisory_only is not True or registry_snapshot_uuid(self.identity_payload())!=self.snapshot_uuid or digest(self.identity_payload())!=self.snapshot_digest): raise ValueError("INVALID_REGISTRY_SNAPSHOT")
    def identity_payload(self): return {n:([list(x) for x in self.record_identities] if n=="record_identities" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"snapshot_uuid","snapshot_digest"}}
    def to_dict(self): return {"snapshot_uuid":self.snapshot_uuid,"snapshot_digest":self.snapshot_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**v):
        v["record_identities"]=tuple(sorted(v["record_identities"])); p={**v,"record_identities":[list(x) for x in v["record_identities"]]}; return cls(snapshot_uuid=registry_snapshot_uuid(p),snapshot_digest=digest(p),**v)

@dataclass(frozen=True)
class KnowledgeRegistryReport:
    report_uuid: str
    source_artifact_type: str
    source_promotion_uuid: str|None
    source_promotion_digest: str|None
    source_promotion_report_uuid: str|None
    source_promotion_report_digest: str|None
    source_promotion_snapshot_uuid: str|None
    source_promotion_snapshot_digest: str|None
    source_promotion_repository_digest: str|None
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    registry_engine_version: str
    registry_admission_policy_uuid: str
    registry_admission_policy_digest: str
    registry_admission_policy_version: str
    registry_records: tuple[RegistryRecord,...]
    processed_record_count: int
    new_registry_record_count: int
    duplicate_registry_record_count: int
    advisory_entry_recorded_count: int
    not_admitted_count: int
    rejected_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool=True
    def __post_init__(self):
        r=tuple(self.registry_records); object.__setattr__(self,"registry_records",r); single=self.source_artifact_type=="PROMOTION_RECORD"; report=self.source_artifact_type=="PATTERN_PROMOTION_REPORT"
        source_ok=(single and valid_uuid(self.source_promotion_uuid) and valid_digest(self.source_promotion_digest) and all(x is None for x in (self.source_promotion_report_uuid,self.source_promotion_report_digest,self.source_promotion_snapshot_uuid,self.source_promotion_snapshot_digest,self.source_promotion_repository_digest))) or (report and self.source_promotion_uuid is None and self.source_promotion_digest is None and all(valid_uuid(x) for x in (self.source_promotion_report_uuid,self.source_promotion_snapshot_uuid)) and all(valid_digest(x) for x in (self.source_promotion_report_digest,self.source_promotion_snapshot_digest,self.source_promotion_repository_digest)))
        counts=tuple(sum(x.registry_state==s for x in r) for s in ("ADVISORY_ENTRY_RECORDED","NOT_ADMITTED","REJECTED")); partition={(x.registry_engine_version,x.registry_admission_policy_uuid,x.registry_admission_policy_digest,x.registry_admission_policy_version,x.source_promotion_engine_version,x.source_promotion_policy_uuid,x.source_promotion_policy_digest,x.source_promotion_policy_version) for x in r}
        expected=(self.registry_engine_version,self.registry_admission_policy_uuid,self.registry_admission_policy_digest,self.registry_admission_policy_version,self.source_promotion_engine_version,self.source_promotion_policy_uuid,self.source_promotion_policy_digest,self.source_promotion_policy_version)
        if (not valid_uuid(self.report_uuid) or not source_ok or not all(valid_uuid(x) for x in (self.source_promotion_policy_uuid,self.registry_admission_policy_uuid,self.snapshot_uuid)) or not all(valid_digest(x) for x in (self.source_promotion_policy_digest,self.registry_admission_policy_digest,self.repository_digest,self.snapshot_digest)) or not _strings((self.source_promotion_engine_version,self.source_promotion_policy_version,self.registry_engine_version,self.registry_admission_policy_version)) or not all(type(x) is RegistryRecord for x in r) or self.processed_record_count!=len(r) or self.new_registry_record_count+self.duplicate_registry_record_count!=len(r) or counts!=(self.advisory_entry_recorded_count,self.not_admitted_count,self.rejected_count) or (partition and partition!={expected}) or not valid_timestamp(self.generated_at) or self.advisory_only is not True or registry_report_uuid(self.identity_payload())!=self.report_uuid): raise ValueError("INVALID_KNOWLEDGE_REGISTRY_REPORT")
    def identity_payload(self): return {n:([x.to_dict() for x in self.registry_records] if n=="registry_records" else getattr(self,n)) for n in self.__dataclass_fields__ if n!="report_uuid"}
    def to_dict(self): return {"report_uuid":self.report_uuid,**self.identity_payload()}
    @classmethod
    def create(cls,**v):
        p={**v,"registry_records":[x.to_dict() for x in v["registry_records"]]}; return cls(report_uuid=registry_report_uuid(p),**v)
