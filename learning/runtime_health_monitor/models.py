"""Immutable advisory-only contracts for PR171 runtime health monitoring."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping, Any
from uuid import UUID
from learning.common.immutable import freeze, thaw

HEALTH_STATES=frozenset({'HEALTHY','DEGRADED','UNSTABLE','STALE','MISMATCH','FAILED','RECOVERING','RECOVERED','UNKNOWN'})
SEVERITIES=frozenset({'INFO','WARNING','ERROR','CRITICAL','EMERGENCY'})
DOMAINS=frozenset({'RUNTIME_HEARTBEAT','ACTIVE_REGISTRY','KNOWLEDGE_VERSION','VERSION_MANIFEST','RUNTIME_GATEWAY','KNOWLEDGE_APPLICABILITY','DECISION_KNOWLEDGE_INTERFACE','ROLLOUT_ADOPTION','ACTIVATION_ADOPTION','ROLLBACK_ADOPTION','CONTRACT_COMPATIBILITY','IDENTITY_CORRELATION','OBSERVABILITY_PIPELINE','REPORTING_PIPELINE'})
LIFECYCLE_STATES=frozenset({'DETECTED','OPEN','ACKNOWLEDGED','INVESTIGATING','ESCALATED','MITIGATION_PENDING','RECOVERING','RESOLVED','SUPPRESSED','EXPIRED','CLOSED'})
RECOMMENDATIONS=frozenset({'INVESTIGATION_REQUIRED','MANUAL_REVIEW_REQUIRED','CONTROLLED_MAINTENANCE_RECOMMENDED','ROLLBACK_REVIEW_RECOMMENDED','EMERGENCY_REVIEW_REQUIRED'})

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)
def digest(v): return sha256(canonical(v).encode()).hexdigest()
def valid_digest(v): return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower())
def valid_uuid(v):
 try: UUID(str(v)); return True
 except (ValueError,TypeError,AttributeError): return False
def valid_time(v):
 try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).tzinfo is not None
 except (ValueError,TypeError,AttributeError): return False
class RuntimeHealthMonitorError(ValueError): pass

def _validate_policy(p):
 nums=('healthy_observation_window_seconds','degraded_threshold_count','unstable_threshold_count','failure_threshold_count','recovery_confirmation_count','incident_deduplication_window_seconds','incident_suppression_window_seconds','incident_expiration_seconds','escalation_warning_seconds','escalation_error_seconds','escalation_critical_seconds','flapping_window_seconds','flapping_transition_threshold','flapping_minimum_duration_seconds')
 if not p.policy_version or not p.architecture_version or not valid_time(p.evaluation_timestamp) or any(not isinstance(getattr(p,n),int) or isinstance(getattr(p,n),bool) or getattr(p,n)<0 for n in nums) or p.allow_automatic_remediation: raise RuntimeHealthMonitorError('INVALID_RUNTIME_HEALTH_POLICY')
@dataclass(frozen=True)
class RuntimeHealthMonitorPolicy:
 policy_version:str='1.0.0'; architecture_version:str='PR171'; evaluation_timestamp:str='1970-01-01T00:00:00Z'; healthy_observation_window_seconds:int=60; degraded_threshold_count:int=2; unstable_threshold_count:int=3; failure_threshold_count:int=2; recovery_confirmation_count:int=2; incident_deduplication_window_seconds:int=300; incident_suppression_window_seconds:int=300; incident_expiration_seconds:int=86400; escalation_warning_seconds:int=300; escalation_error_seconds:int=900; escalation_critical_seconds:int=3600; require_manual_acknowledgement:bool=True; allow_automatic_incident_creation:bool=True; allow_automatic_remediation:bool=False; flapping_window_seconds:int=300; flapping_transition_threshold:int=3; flapping_minimum_duration_seconds:int=0
 def __post_init__(self): _validate_policy(self)
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthEvaluation:
 evaluation_uuid:str; runtime_instance_id:str; knowledge_uuid:str; version_uuid:str; registry_snapshot_digest:str; health_domain:str; state:str; severity:str; reason_code:str; reason_detail:str; source_observation_uuids:tuple[str,...]; source_incident_uuids:tuple[str,...]; evaluation_timestamp:str; policy_version:str; architecture_version:str; evaluation_digest:str; replay_digest:str; advisory_only:bool=True
 def __post_init__(self):
  if not valid_uuid(self.evaluation_uuid) or self.health_domain not in DOMAINS or self.state not in HEALTH_STATES or self.severity not in SEVERITIES or not self.reason_code or not valid_time(self.evaluation_timestamp) or not self.policy_version or not self.architecture_version or not valid_digest(self.evaluation_digest) or not valid_digest(self.replay_digest) or not self.advisory_only or any(not valid_uuid(x) for x in self.source_observation_uuids+self.source_incident_uuids) or (self.knowledge_uuid and not valid_uuid(self.knowledge_uuid)) or (self.version_uuid and not valid_uuid(self.version_uuid)) or (self.registry_snapshot_digest and not valid_digest(self.registry_snapshot_digest)): raise RuntimeHealthMonitorError('INVALID_RUNTIME_HEALTH_EVALUATION')
 def to_dict(self): return {n:list(getattr(self,n)) if n.startswith('source_') else getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthState:
 state_uuid:str; evaluation_uuid:str; state:str; health_domain:str; recorded_at:str; replay_digest:str
 def __post_init__(self):
  if not valid_uuid(self.state_uuid) or not valid_uuid(self.evaluation_uuid) or self.state not in HEALTH_STATES or self.health_domain not in DOMAINS or not valid_time(self.recorded_at) or not valid_digest(self.replay_digest): raise RuntimeHealthMonitorError('INVALID_RUNTIME_HEALTH_STATE')
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthTrend:
 trend_uuid:str; evaluation_uuid:str; state_counts:Mapping[str,int]; consecutive_failures:int; consecutive_stale:int; transitions:int; recorded_at:str; digest:str
 def __post_init__(self):
  if not valid_uuid(self.trend_uuid) or not valid_uuid(self.evaluation_uuid) or not valid_time(self.recorded_at) or not valid_digest(self.digest): raise RuntimeHealthMonitorError('INVALID_RUNTIME_HEALTH_TREND')
  object.__setattr__(self,'state_counts',freeze(dict(self.state_counts)))
 def to_dict(self): return {'trend_uuid':self.trend_uuid,'evaluation_uuid':self.evaluation_uuid,'state_counts':thaw(self.state_counts),'consecutive_failures':self.consecutive_failures,'consecutive_stale':self.consecutive_stale,'transitions':self.transitions,'recorded_at':self.recorded_at,'digest':self.digest}
@dataclass(frozen=True)
class RuntimeHealthIncidentCorrelation:
 correlation_uuid:str; incident_uuid:str; incident_type:str; evaluation_uuid:str; source_observation_uuid:str; correlated_at:str; replay_digest:str
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthIncidentLifecycle:
 lifecycle_uuid:str; incident_uuid:str; state:str; recorded_at:str; reason:str; acknowledged_by:str=''; acknowledged_at:str=''; acknowledgement_reason:str=''; replay_digest:str=''
 def __post_init__(self):
  if not valid_uuid(self.lifecycle_uuid) or not valid_uuid(self.incident_uuid) or self.state not in LIFECYCLE_STATES or not valid_time(self.recorded_at) or not self.reason or (self.acknowledged_at and not valid_time(self.acknowledged_at)) or (self.state=='ACKNOWLEDGED' and (not self.acknowledged_by or not self.acknowledged_at or not self.acknowledgement_reason)) or (self.replay_digest and not valid_digest(self.replay_digest)): raise RuntimeHealthMonitorError('INVALID_INCIDENT_LIFECYCLE')
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthEscalation:
 escalation_uuid:str; incident_uuid:str; severity:str; state:str; assessed_at:str; reason:str; replay_digest:str
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthRecoveryAssessment:
 recovery_assessment_uuid:str; incident_uuid:str; state:str; confirmation_count:int; required_confirmation_count:int; assessed_at:str; reason:str; replay_digest:str
 def __post_init__(self):
  if not valid_uuid(self.recovery_assessment_uuid) or not valid_uuid(self.incident_uuid) or self.state not in {'PENDING','CONFIRMED','REJECTED'} or self.confirmation_count<0 or self.required_confirmation_count<1 or not valid_time(self.assessed_at) or not valid_digest(self.replay_digest): raise RuntimeHealthMonitorError('INVALID_RECOVERY_ASSESSMENT')
 def to_dict(self): return {n:getattr(self,n) for n in self.__dataclass_fields__}
@dataclass(frozen=True)
class RuntimeHealthGovernanceRecommendation:
 recommendation_uuid:str; evaluation_uuid:str; incident_uuid:str; recommendation_type:str; severity:str; reason:str; created_at:str; expires_at:str; policy_version:str; architecture_version:str; evidence_digests:tuple[str,...]; human_review_required:bool=True; executable:bool=False
 def __post_init__(self):
  if not valid_uuid(self.recommendation_uuid) or not valid_uuid(self.evaluation_uuid) or (self.incident_uuid and not valid_uuid(self.incident_uuid)) or self.recommendation_type not in RECOMMENDATIONS or self.severity not in SEVERITIES or not self.reason or not valid_time(self.created_at) or not valid_time(self.expires_at) or not self.policy_version or not self.architecture_version or not self.human_review_required or self.executable or any(not valid_digest(x) for x in self.evidence_digests): raise RuntimeHealthMonitorError('INVALID_GOVERNANCE_RECOMMENDATION')
 def to_dict(self): return {n:list(getattr(self,n)) if n=='evidence_digests' else getattr(self,n) for n in self.__dataclass_fields__}
RuntimeHealthSummary=RuntimeHealthTrend
RuntimeHealthHistory=RuntimeHealthIncidentLifecycle
