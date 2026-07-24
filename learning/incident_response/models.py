"""Immutable, non-executable contracts for PR172 incident response governance."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

STATES=frozenset('CREATED TRIAGED ACKNOWLEDGED ASSIGNED INVESTIGATING ESCALATED RESPONSE_PLANNED ACTION_PENDING MONITORING_RECOVERY RESOLVED POST_INCIDENT_REVIEW CLOSED SUPPRESSED EXPIRED REJECTED'.split())
PRIORITIES=frozenset('P5_INFORMATIONAL P4_LOW P3_MEDIUM P2_HIGH P1_CRITICAL P0_EMERGENCY'.split())
IMPACTS=frozenset('NO_OPERATIONAL_IMPACT LIMITED_OBSERVABILITY_IMPACT DEGRADED_KNOWLEDGE_ASSURANCE RUNTIME_KNOWLEDGE_MISMATCH RUNTIME_SERVICE_DEGRADATION CRITICAL_RUNTIME_RISK UNKNOWN_IMPACT'.split())
CATEGORIES=frozenset('RUNTIME_HEALTH RUNTIME_HEARTBEAT ACTIVE_REGISTRY KNOWLEDGE_VERSION VERSION_MANIFEST RUNTIME_GATEWAY KNOWLEDGE_APPLICABILITY DECISION_KNOWLEDGE ROLLOUT_ADOPTION ACTIVATION_ADOPTION ROLLBACK_ADOPTION CONTRACT_COMPATIBILITY IDENTITY_CORRELATION OBSERVABILITY_PIPELINE HEALTH_MONITOR_PIPELINE REPORTING_PIPELINE SECURITY_GOVERNANCE ARCHITECTURE_VIOLATION UNKNOWN'.split())
SOURCES=frozenset('PR170_OBSERVABILITY PR171_HEALTH_MONITOR MANUAL_OPERATOR GOVERNANCE_REVIEW DEPLOYMENT_REVIEW ACTIVATION_REVIEW ROLLBACK_REVIEW EMERGENCY_REVIEW'.split())
WORKFLOWS=frozenset('OBSERVE_ONLY INVESTIGATE COLLECT_ADDITIONAL_EVIDENCE CONTROLLED_MAINTENANCE_REVIEW ROLLBACK_REVIEW ACTIVATION_REVIEW RUNTIME_DEPLOYMENT_REVIEW EMERGENCY_GOVERNANCE_REVIEW POST_INCIDENT_REVIEW'.split())
RECOMMENDATIONS=frozenset('NO_ACTION_RECOMMENDED CONTINUE_MONITORING ADDITIONAL_EVIDENCE_REQUIRED TECHNICAL_INVESTIGATION_REQUIRED CONTROLLED_MAINTENANCE_REVIEW_REQUIRED RUNTIME_DEPLOYMENT_REVIEW_REQUIRED ACTIVATION_REVIEW_REQUIRED ROLLBACK_REVIEW_REQUIRED EMERGENCY_GOVERNANCE_REVIEW_REQUIRED ARCHITECTURE_REVIEW_REQUIRED'.split())
TIMELINE_EVENTS=frozenset('INCIDENT_CREATED TRIAGE_COMPLETED ACKNOWLEDGED ASSIGNED INVESTIGATION_STARTED EVIDENCE_ADDED ESCALATED RESPONSE_PLAN_CREATED GOVERNANCE_REVIEW_REQUESTED ROLLBACK_REVIEW_REQUESTED MAINTENANCE_REVIEW_REQUESTED RECOVERY_MONITORING_STARTED RECOVERY_CONFIRMED INCIDENT_RESOLVED POST_INCIDENT_REVIEW_STARTED INCIDENT_CLOSED'.split())
TRANSITIONS={'CREATED':{'TRIAGED','REJECTED','EXPIRED'},'TRIAGED':{'ACKNOWLEDGED','SUPPRESSED'},'ACKNOWLEDGED':{'ASSIGNED'},'ASSIGNED':{'INVESTIGATING'},'INVESTIGATING':{'ESCALATED','RESPONSE_PLANNED'},'ESCALATED':{'RESPONSE_PLANNED'},'RESPONSE_PLANNED':{'ACTION_PENDING'},'ACTION_PENDING':{'MONITORING_RECOVERY'},'MONITORING_RECOVERY':{'RESOLVED'},'RESOLVED':{'POST_INCIDENT_REVIEW'},'POST_INCIDENT_REVIEW':{'CLOSED'}}
def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str)
def digest(v): return sha256(canonical(v).encode()).hexdigest()
def valid_digest(v): return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v.lower())
def valid_uuid(v):
 try: UUID(str(v)); return True
 except (ValueError,TypeError,AttributeError): return False
def valid_time(v):
 try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).tzinfo is not None
 except (ValueError,TypeError,AttributeError): return False
class IncidentResponseError(ValueError): pass
@dataclass(frozen=True)
class IncidentResponsePolicy:
 policy_version:str='1.0.0'; architecture_version:str='PR172'; evaluation_timestamp:str='1970-01-01T00:00:00Z'; deduplication_window_seconds:int=300; correlation_window_seconds:int=300; acknowledgement_timeout_seconds:int=300; assignment_timeout_seconds:int=900; investigation_timeout_seconds:int=3600; escalation_timeout_seconds:int=1800; response_plan_ttl_seconds:int=86400; incident_expiration_seconds:int=86400; require_manual_acknowledgement:bool=True; require_human_assignment:bool=True; require_human_closure:bool=True; require_post_incident_review:bool=True; allow_automatic_case_creation:bool=True; allow_automatic_execution:bool=False
 def __post_init__(self):
  if not self.policy_version or not self.architecture_version or not valid_time(self.evaluation_timestamp) or self.allow_automatic_execution or any(not isinstance(getattr(self,n),int) or getattr(self,n)<0 for n in self.__dataclass_fields__ if n.endswith('_seconds')): raise IncidentResponseError('INVALID_INCIDENT_RESPONSE_POLICY')
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentCase:
 incident_case_uuid:str; source_incident_uuid:str; incident_category:str; source:str; runtime_instance_id:str; knowledge_uuid:str; version_uuid:str; registry_snapshot_digest:str; incident_window_start:str; state:str; priority:str; impact:str; evidence_digest:str; replay_digest:str; policy_version:str; architecture_version:str
 def __post_init__(self):
  if not valid_uuid(self.incident_case_uuid) or (self.source_incident_uuid and not valid_uuid(self.source_incident_uuid)) or self.incident_category not in CATEGORIES or self.source not in SOURCES or self.state not in STATES or self.priority not in PRIORITIES or self.impact not in IMPACTS or not valid_time(self.incident_window_start) or not valid_digest(self.evidence_digest) or not valid_digest(self.replay_digest) or not self.policy_version or not self.architecture_version or (self.knowledge_uuid and not valid_uuid(self.knowledge_uuid)) or (self.version_uuid and not valid_uuid(self.version_uuid)) or (self.registry_snapshot_digest and not valid_digest(self.registry_snapshot_digest)): raise IncidentResponseError('INVALID_INCIDENT_CASE')
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentTriageAssessment:
 triage_uuid:str; incident_case_uuid:str; priority:str; impact:str; evidence_complete:bool; evidence_integrity:bool; workflow_type:str; assessed_at:str; replay_digest:str
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentScopeAssessment:
 scope_uuid:str; incident_case_uuid:str; affected_runtime_instances:tuple[str,...]=(); affected_symbols:tuple[str,...]=(); affected_sessions:tuple[str,...]=(); affected_knowledge_uuids:tuple[str,...]=(); affected_version_uuids:tuple[str,...]=(); affected_registry_snapshots:tuple[str,...]=(); affected_rollouts:tuple[str,...]=(); affected_activations:tuple[str,...]=(); affected_rollbacks:tuple[str,...]=(); affected_contracts:tuple[str,...]=(); scope_confidence:str='UNKNOWN'
 def to_dict(self): return {k:list(v) if isinstance(v,tuple) else v for k,v in self.__dict__.items()}
@dataclass(frozen=True)
class IncidentAssignment:
 assignment_uuid:str; incident_case_uuid:str; assigned_to:str; assigned_by:str; assigned_at:str; assignment_reason:str; assignment_role:str; replay_digest:str
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentAcknowledgement:
 acknowledgement_uuid:str; incident_case_uuid:str; acknowledged_by:str; acknowledged_at:str; acknowledgement_reason:str; replay_digest:str
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentResponseWorkflow:
 workflow_uuid:str; incident_case_uuid:str; workflow_type:str; selected_at:str; policy_version:str; replay_digest:str
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentResponsePlan:
 plan_uuid:str; incident_case_uuid:str; response_type:str; created_at:str; expires_at:str; policy_version:str; architecture_version:str; required_investigators:tuple[str,...]=(); required_evidence:tuple[str,...]=(); required_approvals:tuple[str,...]=(); recommended_actions:tuple[str,...]=(); prohibited_actions:tuple[str,...]=('runtime mutation','registry mutation','activation','rollback execution','maintenance execution'); execution_authority_required:bool=True; rollback_review_required:bool=False; maintenance_review_required:bool=False; emergency_review_required:bool=False; verification_steps:tuple[str,...]=(); closure_criteria:tuple[str,...]=(); executable:bool=False
 def __post_init__(self):
  if self.response_type not in WORKFLOWS or not valid_uuid(self.plan_uuid) or not valid_uuid(self.incident_case_uuid) or not valid_time(self.created_at) or not valid_time(self.expires_at) or not self.policy_version or not self.architecture_version or self.executable: raise IncidentResponseError('INVALID_INCIDENT_RESPONSE_PLAN')
 def to_dict(self): return {k:list(v) if isinstance(v,tuple) else v for k,v in self.__dict__.items()}
@dataclass(frozen=True)
class IncidentGovernanceRecommendation:
 recommendation_uuid:str; incident_case_uuid:str; recommendation_type:str; reason:str; created_at:str; executable:bool=False
 def __post_init__(self):
  if self.recommendation_type not in RECOMMENDATIONS or not self.reason or self.executable: raise IncidentResponseError('INVALID_INCIDENT_RECOMMENDATION')
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentTimelineEvent:
 event_uuid:str; incident_case_uuid:str; event_type:str; actor:str; occurred_at:str; source_artifact_uuid:str; source_artifact_digest:str; reason:str; policy_version:str; architecture_version:str
 def __post_init__(self):
  if not valid_uuid(self.event_uuid) or not valid_uuid(self.incident_case_uuid) or self.event_type not in TIMELINE_EVENTS or not self.actor or not valid_time(self.occurred_at) or (self.source_artifact_uuid and not valid_uuid(self.source_artifact_uuid)) or not valid_digest(self.source_artifact_digest) or not self.reason or not self.policy_version or not self.architecture_version: raise IncidentResponseError('INVALID_INCIDENT_TIMELINE_EVENT')
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentRootCauseAnalysis:
 rca_uuid:str; incident_case_uuid:str; state:str; problem_statement:str; observed_symptoms:tuple[dict,...]; candidate_causes:tuple[dict,...]; analyst_identity:str; created_at:str; policy_version:str; architecture_version:str; confidence:str='UNKNOWN'; completed_at:str=''; confirmed_cause:str=''
 def __post_init__(self):
  if self.state not in {'NOT_STARTED','EVIDENCE_COLLECTION','ANALYSIS_IN_PROGRESS','HYPOTHESIS_IDENTIFIED','CAUSE_CONFIRMED','CAUSE_UNCONFIRMED','INCONCLUSIVE'} or any(x.get('classification') not in {'OBSERVED_FACT','SUPPORTED_INFERENCE','UNVERIFIED_HYPOTHESIS'} for x in self.observed_symptoms+self.candidate_causes): raise IncidentResponseError('INVALID_INCIDENT_RCA')
 def to_dict(self): return {k:list(v) if isinstance(v,tuple) else v for k,v in self.__dict__.items()}
@dataclass(frozen=True)
class PostIncidentReview:
 review_uuid:str; incident_case_uuid:str; incident_summary:str; impact_summary:str; reviewed_by:str; reviewed_at:str; review_digest:str
 def to_dict(self): return dict(self.__dict__)
@dataclass(frozen=True)
class IncidentClosureRecord:
 closure_uuid:str; incident_case_uuid:str; approved_by:str; closed_at:str; reason:str; replay_digest:str
 def to_dict(self): return dict(self.__dict__)
IncidentCorrelation=IncidentScopeAssessment; IncidentEscalation=IncidentGovernanceRecommendation; IncidentResolutionAssessment=IncidentGovernanceRecommendation; IncidentResponseHistory=IncidentTimelineEvent; IncidentResponseAudit=IncidentTimelineEvent
