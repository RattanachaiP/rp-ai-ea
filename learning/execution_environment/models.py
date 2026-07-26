"""Immutable PR187 environment evidence, result, report, and snapshot artifacts."""
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.execution_readiness.models import EXECUTION_READINESS_STATES
from .identity import digest, environment_evidence_uuid, execution_environment_uuid, report_uuid, snapshot_uuid
from .policy import ENVIRONMENT_DIMENSIONS, ExecutionEnvironmentPolicy

AUTHORITY_SCOPE = "ADVISORY_EXECUTION_ENVIRONMENT_ONLY"
EXECUTION_ENVIRONMENT_STATES = ("REJECTED", "INSUFFICIENT_ENVIRONMENT_INFORMATION", "ENVIRONMENT_READY_FOR_FEASIBILITY")


def _version(value): return isinstance(value, str) and bool(value) and value == value.strip()
def _partition_valid(uuid, dgst, version, engine): return valid_uuid(uuid) and valid_digest(dgst) and _version(version) and _version(engine)

@dataclass(frozen=True)
class ExecutionEnvironmentEvidence:
    evidence_uuid: str
    evidence_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    advisory_only: bool = True

    def __post_init__(self):
        observations = tuple(tuple(x) for x in self.observations)
        object.__setattr__(self, "observations", observations)
        names = tuple(x[0] for x in observations if len(x) == 2)
        canonical = tuple(x for x in ENVIRONMENT_DIMENSIONS if x in names)
        if (not valid_uuid(self.evidence_uuid) or not valid_digest(self.evidence_digest)
            or not valid_uuid(self.execution_readiness_uuid) or not valid_digest(self.execution_readiness_digest)
            or any(len(x) != 2 for x in observations) or len(names) != len(set(names)) or names != canonical
            or any(type(v) is not float or not isfinite(v) or v < 0 for _, v in observations)
            or not valid_timestamp(self.captured_at)
            or not _partition_valid(self.readiness_policy_uuid, self.readiness_policy_digest, self.readiness_policy_version, self.readiness_engine_version)
            or self.advisory_only is not True
            or environment_evidence_uuid(self.identity_payload()) != self.evidence_uuid
            or digest(self.digest_payload()) != self.evidence_digest):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_EVIDENCE")

    def identity_payload(self):
        return {n: ([list(x) for x in self.observations] if n == "observations" else getattr(self, n)) for n in self.__dataclass_fields__ if n not in {"evidence_uuid", "evidence_digest"}}
    def digest_payload(self): return {"evidence_uuid": self.evidence_uuid, **self.identity_payload()}
    def to_dict(self): return {**self.digest_payload(), "evidence_digest": self.evidence_digest}
    @classmethod
    def create(cls, **values):
        values = dict(values); values["observations"] = tuple(values["observations"])
        observations = values["observations"]
        names = tuple(x[0] for x in observations if len(x) == 2)
        if (any(len(x) != 2 for x in observations)
            or len(names) != len(set(names))
            or names != tuple(x for x in ENVIRONMENT_DIMENSIONS if x in names)
            or any(type(v) is not float or not isfinite(v) or v < 0 for _, v in observations)):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_EVIDENCE")
        payload = {**values, "observations": [list(x) for x in values["observations"]]}
        uid = environment_evidence_uuid(payload)
        return cls(evidence_uuid=uid, evidence_digest=digest({"evidence_uuid": uid, **payload}), **values)

@dataclass(frozen=True)
class ExecutionEnvironment:
    execution_environment_uuid: str
    execution_environment_digest: str
    execution_readiness_uuid: str
    execution_readiness_digest: str
    readiness_state: str
    evidence_uuid: str | None
    evidence_digest: str | None
    environment_evidence_complete: bool
    environment_state: str
    environment_reason: str
    environment_profile: tuple[tuple[str, str], ...]
    environment_quality: float
    readiness_snapshot_uuid: str
    readiness_snapshot_digest: str
    readiness_repository_digest: str
    environment_policy: Mapping
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        profile = tuple(tuple(x) for x in self.environment_profile); object.__setattr__(self, "environment_profile", profile)
        policy_data = dict(self.environment_policy); object.__setattr__(self, "environment_policy", policy_data)
        try: policy = ExecutionEnvironmentPolicy(**policy_data)
        except (TypeError, ValueError): policy = None
        names = tuple(x[0] for x in profile if len(x) == 2)
        evidence_pair = (self.evidence_uuid is None and self.evidence_digest is None) or (valid_uuid(self.evidence_uuid) and valid_digest(self.evidence_digest))
        expected_state = "REJECTED" if self.readiness_state == "REJECTED" else ("ENVIRONMENT_READY_FOR_FEASIBILITY" if self.evidence_uuid is not None and self.environment_evidence_complete is True and self.environment_quality >= (policy.minimum_quality if policy else 2) else "INSUFFICIENT_ENVIRONMENT_INFORMATION")
        expected_reason = {"REJECTED":"READINESS_REJECTED", "ENVIRONMENT_READY_FOR_FEASIBILITY":"ENVIRONMENT_QUALITY_SUFFICIENT", "INSUFFICIENT_ENVIRONMENT_INFORMATION":"ENVIRONMENT_EVIDENCE_INSUFFICIENT"}[expected_state]
        if (not valid_uuid(self.execution_environment_uuid) or not valid_digest(self.execution_environment_digest)
            or not valid_uuid(self.execution_readiness_uuid) or not valid_digest(self.execution_readiness_digest)
            or self.readiness_state not in EXECUTION_READINESS_STATES or not evidence_pair
            or type(self.environment_evidence_complete) is not bool
            or len(profile) != len(ENVIRONMENT_DIMENSIONS) or names != ENVIRONMENT_DIMENSIONS
            or any(v not in {"AVAILABLE", "UNAVAILABLE"} for _, v in profile)
            or type(self.environment_quality) is not float or not isfinite(self.environment_quality) or not 0 <= self.environment_quality <= 1
            or self.environment_quality != sum(v == "AVAILABLE" for _, v in profile) / len(profile)
            or self.environment_state != expected_state or self.environment_reason != expected_reason
            or policy is None or self.environment_policy_uuid != policy.environment_policy_uuid or self.environment_policy_digest != policy.environment_policy_digest
            or self.environment_policy_version != policy.environment_policy_version or self.environment_engine_version != policy.environment_engine_version
            or not valid_uuid(self.readiness_snapshot_uuid) or not valid_digest(self.readiness_snapshot_digest) or not valid_digest(self.readiness_repository_digest)
            or not valid_timestamp(self.created_at) or self.authority_scope != AUTHORITY_SCOPE or self.advisory_only is not True
            or execution_environment_uuid(self.identity_payload()) != self.execution_environment_uuid or digest(self.digest_payload()) != self.execution_environment_digest):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT")

    def identity_payload(self):
        return {n: ([list(x) for x in self.environment_profile] if n == "environment_profile" else dict(self.environment_policy) if n == "environment_policy" else getattr(self, n)) for n in self.__dataclass_fields__ if n not in {"execution_environment_uuid", "execution_environment_digest"}}
    def digest_payload(self): return {"execution_environment_uuid": self.execution_environment_uuid, **self.identity_payload()}
    def to_dict(self): return {**self.digest_payload(), "execution_environment_digest": self.execution_environment_digest}
    @classmethod
    def create(cls, **values):
        uid = execution_environment_uuid(values); return cls(execution_environment_uuid=uid, execution_environment_digest=digest({"execution_environment_uuid": uid, **values}), **values)

@dataclass(frozen=True)
class ExecutionEnvironmentSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    environment_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    environment_policy_uuid: str
    environment_policy_digest: str
    environment_policy_version: str
    environment_engine_version: str
    readiness_policy_uuid: str
    readiness_policy_digest: str
    readiness_policy_version: str
    readiness_engine_version: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        ids=tuple(tuple(x) for x in self.environment_identities); object.__setattr__(self,"environment_identities",ids)
        prev=(self.previous_snapshot_uuid is None and self.previous_snapshot_digest is None) or (valid_uuid(self.previous_snapshot_uuid) and valid_digest(self.previous_snapshot_digest))
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or not valid_digest(self.repository_digest)
            or ids != tuple(sorted(ids)) or self.record_count != len(ids) or len({x[0] for x in ids}) != len(ids)
            or any(not valid_uuid(x[0]) or not valid_digest(x[1]) for x in ids) or not prev
            or not _partition_valid(self.environment_policy_uuid,self.environment_policy_digest,self.environment_policy_version,self.environment_engine_version)
            or not _partition_valid(self.readiness_policy_uuid,self.readiness_policy_digest,self.readiness_policy_version,self.readiness_engine_version)
            or not valid_timestamp(self.generated_at) or self.authority_scope != AUTHORITY_SCOPE or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid or digest(self.identity_payload()) != self.snapshot_digest):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_SNAPSHOT")
    def identity_payload(self): return {n: ([list(x) for x in self.environment_identities] if n=="environment_identities" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"snapshot_uuid","snapshot_digest"}}
    def to_dict(self): return {"snapshot_uuid":self.snapshot_uuid,"snapshot_digest":self.snapshot_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**values):
        values=dict(values); values["environment_identities"]=tuple(values["environment_identities"]); payload={**values,"environment_identities":[list(x) for x in values["environment_identities"]]}; uid=snapshot_uuid(payload); return cls(snapshot_uuid=uid,snapshot_digest=digest(payload),**values)

@dataclass(frozen=True)
class ExecutionEnvironmentReport:
    report_uuid: str
    report_digest: str
    execution_environment_records: tuple[ExecutionEnvironment,...]
    processed_count: int
    ready_count: int
    insufficient_count: int
    rejected_count: int
    duplicate_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    advisory_only: bool=True
    def __post_init__(self):
        items=tuple(ExecutionEnvironment(**x) if isinstance(x,Mapping) else x for x in self.execution_environment_records); object.__setattr__(self,"execution_environment_records",items)
        if (any(type(x) is not ExecutionEnvironment for x in items) or self.processed_count != len(items)
            or self.ready_count != sum(x.environment_state=="ENVIRONMENT_READY_FOR_FEASIBILITY" for x in items)
            or self.insufficient_count != sum(x.environment_state=="INSUFFICIENT_ENVIRONMENT_INFORMATION" for x in items)
            or self.rejected_count != sum(x.environment_state=="REJECTED" for x in items)
            or len({x.execution_environment_uuid for x in items}) != len(items) or type(self.duplicate_count) is not int or not 0<=self.duplicate_count<=len(items)
            or not valid_uuid(self.report_uuid) or not valid_digest(self.report_digest) or not valid_digest(self.repository_digest)
            or not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest) or not valid_timestamp(self.generated_at) or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid or digest(self.digest_payload()) != self.report_digest): raise ValueError("INVALID_EXECUTION_ENVIRONMENT_REPORT")
    def identity_payload(self): return {n:([x.to_dict() for x in self.execution_environment_records] if n=="execution_environment_records" else getattr(self,n)) for n in self.__dataclass_fields__ if n not in {"report_uuid","report_digest"}}
    def digest_payload(self): return {"report_uuid":self.report_uuid,**self.identity_payload()}
    def to_dict(self): return {"report_uuid":self.report_uuid,"report_digest":self.report_digest,**self.identity_payload()}
    @classmethod
    def create(cls,**values):
        values=dict(values); values["execution_environment_records"]=tuple(values["execution_environment_records"]); payload={**values,"execution_environment_records":[x.to_dict() for x in values["execution_environment_records"]]}; uid=report_uuid(payload); return cls(report_uuid=uid,report_digest=digest({"report_uuid":uid,**payload}),**values)
