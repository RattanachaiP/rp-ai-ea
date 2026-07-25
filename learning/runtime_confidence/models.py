"""Immutable advisory-only PR182 confidence artifacts."""
from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import confidence_uuid, digest, report_uuid, snapshot_uuid

STATES = ("REJECTED", "INSUFFICIENT_CONFIDENCE_EVIDENCE", "CONFIDENCE_EVALUATED")
PARTITION_FIELDS = ("confidence_policy_uuid", "confidence_policy_digest", "confidence_policy_version", "confidence_engine_version")

@dataclass(frozen=True)
class ConfidenceRecord:
    confidence_uuid: str; confidence_digest: str; eligibility_uuid: str; eligibility_digest: str
    runtime_package_uuid: str; registry_uuid: str; promotion_uuid: str; validation_uuid: str
    memory_uuid: str; pattern_uuid: str; knowledge_uuid: str
    confidence_state: str; confidence_reason: str; confidence_score: float
    confidence_policy_uuid: str; confidence_policy_digest: str; confidence_policy_version: str
    confidence_engine_version: str; created_at: str; advisory_only: bool = True
    def __post_init__(self):
        uuids=(self.confidence_uuid,self.eligibility_uuid,self.runtime_package_uuid,self.registry_uuid,self.promotion_uuid,self.validation_uuid,self.memory_uuid,self.pattern_uuid,self.knowledge_uuid,self.confidence_policy_uuid)
        if (not all(valid_uuid(x) for x in uuids) or not valid_digest(self.confidence_digest)
            or not valid_digest(self.eligibility_digest) or self.confidence_state not in STATES
            or not self.confidence_reason or type(self.confidence_score) is not float
            or not 0.0 <= self.confidence_score <= 1.0 or not self.confidence_policy_version
            or not self.confidence_engine_version or not valid_digest(self.confidence_policy_digest)
            or not valid_timestamp(self.created_at) or self.advisory_only is not True
            or confidence_uuid(self.identity_payload()) != self.confidence_uuid
            or digest(self.digest_payload()) != self.confidence_digest):
            raise ValueError("INVALID_CONFIDENCE_RECORD")
    def identity_payload(self): return {n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"confidence_uuid","confidence_digest"}}
    def digest_payload(self): return {"confidence_uuid":self.confidence_uuid,**self.identity_payload()}
    def to_dict(self): return {"confidence_uuid":self.confidence_uuid,"confidence_digest":self.confidence_digest,**self.identity_payload()}
    @classmethod
    def create(cls, **v):
        i=confidence_uuid(v); return cls(confidence_uuid=i,confidence_digest=digest({"confidence_uuid":i,**v}),**v)

@dataclass(frozen=True)
class ConfidenceSnapshot:
    snapshot_uuid: str; snapshot_digest: str
    confidence_policy_uuid: str; confidence_policy_digest: str; confidence_policy_version: str; confidence_engine_version: str
    confidence_identities: tuple[tuple[str,str],...]; record_count: int; repository_digest: str
    previous_snapshot_uuid: str|None; previous_snapshot_digest: str|None; generated_at: str; advisory_only: bool=True
    def __post_init__(self):
        ids=tuple(sorted(tuple(x) for x in self.confidence_identities)); object.__setattr__(self,"confidence_identities",ids)
        previous=(self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest))
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or not valid_uuid(self.confidence_policy_uuid)
            or not valid_digest(self.confidence_policy_digest) or not self.confidence_policy_version or not self.confidence_engine_version
            or self.record_count != len(ids) or len({x[0] for x in ids}) != len(ids)
            or not all(valid_uuid(x[0]) and valid_digest(x[1]) for x in ids) or not valid_digest(self.repository_digest)
            or not previous or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_CONFIDENCE_SNAPSHOT")
    def identity_payload(self): return {n:([list(x) for x in self.confidence_identities] if n=="confidence_identities" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"snapshot_uuid","snapshot_digest"}}
    def to_dict(self): return {"snapshot_uuid":self.snapshot_uuid,"snapshot_digest":self.snapshot_digest,**self.identity_payload()}
    @classmethod
    def create(cls, **v):
        v=dict(v); v["confidence_identities"]=tuple(sorted(tuple(x) for x in v["confidence_identities"])); payload={**v,"confidence_identities":[list(x) for x in v["confidence_identities"]]}
        return cls(snapshot_uuid=snapshot_uuid(payload),snapshot_digest=digest(payload),**v)

@dataclass(frozen=True)
class RuntimeConfidenceReport:
    report_uuid: str; report_digest: str; confidence_records: tuple[ConfidenceRecord,...]
    processed_record_count: int; confidence_evaluated_count: int; insufficient_confidence_count: int
    rejected_count: int; duplicate_count: int; repository_digest: str; snapshot_uuid: str; snapshot_digest: str
    confidence_policy_uuid: str; confidence_policy_digest: str; confidence_policy_version: str; confidence_engine_version: str
    generated_at: str; advisory_only: bool=True
    def __post_init__(self):
        records=tuple(self.confidence_records); object.__setattr__(self,"confidence_records",records); counts=(self.processed_record_count,self.confidence_evaluated_count,self.insufficient_confidence_count,self.rejected_count,self.duplicate_count)
        if (not valid_uuid(self.report_uuid) or not valid_digest(self.report_digest) or not all(type(x) is int and x>=0 for x in counts)
            or self.processed_record_count != len(records) or sum(counts[1:4]) != len(records) or self.duplicate_count > len(records)
            or not all(type(x) is ConfidenceRecord for x in records)
            or self.confidence_evaluated_count != sum(x.confidence_state=="CONFIDENCE_EVALUATED" for x in records)
            or self.insufficient_confidence_count != sum(x.confidence_state=="INSUFFICIENT_CONFIDENCE_EVIDENCE" for x in records)
            or self.rejected_count != sum(x.confidence_state=="REJECTED" for x in records)
            or not valid_digest(self.repository_digest) or not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
            or not valid_uuid(self.confidence_policy_uuid) or not valid_digest(self.confidence_policy_digest)
            or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid or digest(self.digest_payload()) != self.report_digest): raise ValueError("INVALID_CONFIDENCE_REPORT")
    def identity_payload(self): return {n:([x.to_dict() for x in self.confidence_records] if n=="confidence_records" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"report_uuid","report_digest"}}
    def digest_payload(self): return {"report_uuid":self.report_uuid,**self.identity_payload()}
    def to_dict(self): return {"report_uuid":self.report_uuid,"report_digest":self.report_digest,**self.identity_payload()}
    @classmethod
    def create(cls, **v):
        v=dict(v); v["confidence_records"]=tuple(v["confidence_records"]); payload={**v,"confidence_records":[x.to_dict() for x in v["confidence_records"]]}; i=report_uuid(payload)
        return cls(report_uuid=i,report_digest=digest({"report_uuid":i,**payload}),**v)
