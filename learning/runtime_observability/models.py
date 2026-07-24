"""Immutable, passive contracts for PR170 runtime knowledge observability."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import UUID
from learning.common.immutable import freeze, thaw

OBSERVATION_TYPES=frozenset({'REGISTRY_STATE_OBSERVATION','KNOWLEDGE_VERSION_OBSERVATION','GATEWAY_LOAD_OBSERVATION','APPLICABILITY_OBSERVATION','DECISION_KNOWLEDGE_OBSERVATION','RUNTIME_HEARTBEAT_OBSERVATION','ROLLOUT_HEALTH_OBSERVATION','ACTIVATION_ADOPTION_OBSERVATION','ROLLBACK_ADOPTION_OBSERVATION','CONTRACT_COMPATIBILITY_OBSERVATION','RUNTIME_EXCEPTION_OBSERVATION','STALE_STATE_OBSERVATION','IDENTITY_MISMATCH_OBSERVATION'})
OBSERVATION_STATES=frozenset({'HEALTHY','DEGRADED','STALE','MISMATCH','FAILED','UNKNOWN'})
ADOPTION_STATES=frozenset({'ADOPTION_CONFIRMED','ADOPTION_PENDING','ADOPTION_MISMATCH','ADOPTION_STALE','ADOPTION_UNKNOWN'})
SEVERITIES=frozenset({'INFO','WARNING','ERROR','CRITICAL'})

def canonical(value: Any)->str: return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)
def digest(value: Any)->str: return sha256(canonical(value).encode()).hexdigest()
def valid_digest(v: object)->bool: return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower())
def valid_uuid(v: object)->bool:
    try: UUID(str(v)); return True
    except (ValueError,TypeError,AttributeError): return False
def valid_time(v: object)->bool:
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).tzinfo is not None
    except (ValueError,TypeError,AttributeError): return False

def payload(value): return value.to_dict() if hasattr(value,'to_dict') else (asdict(value) if hasattr(value,'__dataclass_fields__') else dict(value))

class RuntimeKnowledgeObservabilityError(ValueError): pass
@dataclass(frozen=True)
class RuntimeKnowledgeObservabilityPolicy:
    policy_version:str='1.0.0'; architecture_version:str='PR170'; evaluation_timestamp:str='1970-01-01T00:00:00Z'; registry_stale_seconds:int=300; heartbeat_stale_seconds:int=60; gateway_receipt_stale_seconds:int=300; applicability_stale_seconds:int=300; decision_snapshot_stale_seconds:int=300; rollout_receipt_stale_seconds:int=300; severity_policy:Mapping[str,str]=field(default_factory=dict)
    def __post_init__(self):
        if not self.policy_version or not self.architecture_version or not valid_time(self.evaluation_timestamp) or any(not isinstance(getattr(self,n),int) or getattr(self,n)<0 for n in ('registry_stale_seconds','heartbeat_stale_seconds','gateway_receipt_stale_seconds','applicability_stale_seconds','decision_snapshot_stale_seconds','rollout_receipt_stale_seconds')): raise RuntimeKnowledgeObservabilityError('INVALID_OBSERVABILITY_POLICY')
        if any(v not in SEVERITIES for v in self.severity_policy.values()): raise RuntimeKnowledgeObservabilityError('INVALID_SEVERITY_POLICY')
        object.__setattr__(self,'severity_policy',freeze(dict(self.severity_policy)))
    def to_dict(self): return {n:thaw(getattr(self,n)) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeKnowledgeObservation:
    observation_uuid:str; observation_type:str; runtime_instance_id:str; knowledge_uuid:str; version_uuid:str; registry_snapshot_digest:str; observed_at:str; evaluation_timestamp:str; state:str; reason_code:str; reason_detail:str; source_authority:str; source_artifact_digest:str; architecture_version:str; policy_version:str; replay_digest:str
    def __post_init__(self):
        if not valid_uuid(self.observation_uuid) or self.observation_type not in OBSERVATION_TYPES or self.state not in OBSERVATION_STATES or not valid_time(self.observed_at) or not valid_time(self.evaluation_timestamp) or not self.runtime_instance_id or not self.source_authority or not valid_digest(self.source_artifact_digest) or not valid_digest(self.replay_digest) or not self.architecture_version or not self.policy_version or (self.knowledge_uuid and not valid_uuid(self.knowledge_uuid)) or (self.version_uuid and not valid_uuid(self.version_uuid)) or (self.registry_snapshot_digest and not valid_digest(self.registry_snapshot_digest)): raise RuntimeKnowledgeObservabilityError('INVALID_RUNTIME_KNOWLEDGE_OBSERVATION')
    def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class KnowledgeIdentityCorrelation:
    knowledge_uuid:str=''; version_uuid:str=''; activation_uuid:str=''; promotion_uuid:str=''; rollback_uuid:str=''; registry_snapshot_digest:str=''; manifest_digest:str=''; version_digest:str=''; rollout_uuid:str=''; runtime_instance_id:str=''; decision_id:str=''; state:str='UNKNOWN'; reason:str='MISSING_EVIDENCE'
    def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class KnowledgeAdoptionAssessment:
    adoption_state:str; knowledge_uuid:str; version_uuid:str; runtime_instance_id:str; assessed_at:str; reason_code:str; evidence_digest:str
    def __post_init__(self):
        if self.adoption_state not in ADOPTION_STATES or not valid_time(self.assessed_at) or not valid_digest(self.evidence_digest): raise RuntimeKnowledgeObservabilityError('INVALID_ADOPTION_ASSESSMENT')
    def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class ContractCompatibilityAssessment:
    compatible:bool; dimensions:Mapping[str,str]; assessed_at:str; reason_code:str; digest:str
    def __post_init__(self):
        if not isinstance(self.compatible,bool) or not valid_time(self.assessed_at) or not valid_digest(self.digest): raise RuntimeKnowledgeObservabilityError('INVALID_COMPATIBILITY_ASSESSMENT')
        object.__setattr__(self,'dimensions',freeze(dict(self.dimensions)))
    def to_dict(self): return {'compatible':self.compatible,'dimensions':thaw(self.dimensions),'assessed_at':self.assessed_at,'reason_code':self.reason_code,'digest':self.digest}
@dataclass(frozen=True)
class RuntimeKnowledgeHealthSnapshot:
    snapshot_uuid:str; evaluated_at:str; dimensions:Mapping[str,str]; overall_state:str; digest:str
    def __post_init__(self):
        if not valid_uuid(self.snapshot_uuid) or not valid_time(self.evaluated_at) or self.overall_state not in OBSERVATION_STATES or not valid_digest(self.digest): raise RuntimeKnowledgeObservabilityError('INVALID_HEALTH_SNAPSHOT')
        object.__setattr__(self,'dimensions',freeze(dict(self.dimensions)))
    def to_dict(self): return {'snapshot_uuid':self.snapshot_uuid,'evaluated_at':self.evaluated_at,'dimensions':thaw(self.dimensions),'overall_state':self.overall_state,'digest':self.digest}
@dataclass(frozen=True)
class RuntimeKnowledgeIncident:
    incident_uuid:str; observation_uuid:str; classification:str; severity:str; detected_at:str; evidence_digest:str; resolved:bool=False
    def __post_init__(self):
        if not valid_uuid(self.incident_uuid) or not valid_uuid(self.observation_uuid) or not self.classification or self.severity not in SEVERITIES or not valid_time(self.detected_at) or not valid_digest(self.evidence_digest): raise RuntimeKnowledgeObservabilityError('INVALID_RUNTIME_KNOWLEDGE_INCIDENT')
    def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
RuntimeKnowledgeIncidentEvidence=RuntimeKnowledgeIncident
@dataclass(frozen=True)
class RuntimeKnowledgeObservabilitySummary:
    total_observations:int; states:Mapping[str,int]; digest:str
    def to_dict(self): return {'total_observations':self.total_observations,'states':dict(self.states),'digest':self.digest}
