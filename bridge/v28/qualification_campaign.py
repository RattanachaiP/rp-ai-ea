"""Authoritative immutable PR266 run and campaign evidence contracts."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from .certification_report import CertificationReport
from .delivery_pipeline_validator import DeliveryValidationReport
from .execution_bridge import DeliveryReceipt
from .execution_plan import identity, parse_utc
from .pipeline_validator import PR265_POLICY, PipelineValidationReport, certification_identity, report_identity_valid
from .publisher_contract import PublishedExecutionPlan, RuntimeHealthSnapshot
from .qualification_policy import QualificationPolicy

ACTIONS=("BUY","SELL","HOLD")
def canonical_utc(value:str|datetime)->str:
    parsed=value if isinstance(value,datetime) else parse_utc(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:raise ValueError("TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

@dataclass(frozen=True)
class QualificationScenario:
    family_identity:str;action:str;fixture_identity:str;normalized_input_identity:str
    expected_semantic_output_identity:str;scenario_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="scenario_identity"}
    def __post_init__(self):
        if self.action not in ACTIONS or not all((self.family_identity,self.fixture_identity,self.normalized_input_identity,self.expected_semantic_output_identity)):raise ValueError("QUALIFICATION_SCENARIO_INVALID")
        if self.scenario_identity!=certification_identity("V28_QUALIFICATION_SCENARIO",self.canonical_payload()):raise ValueError("QUALIFICATION_SCENARIO_IDENTITY_INVALID")
def create_scenario(**values:Any)->QualificationScenario:return QualificationScenario(**values,scenario_identity=certification_identity("V28_QUALIFICATION_SCENARIO",values))
def normalized_projection_identity(*,family_identity:str,fixture_identity:str,symbol:str,environment_identity:str,action:str)->str:
    return certification_identity("V28_QUALIFICATION_NORMALIZED_INPUT",dict(family_identity=family_identity,fixture_identity=fixture_identity,symbol=symbol,environment_identity=environment_identity,action=action))

def semantic_output_identity(certification:CertificationReport,action:str)->str:
    records=tuple(x for x in certification.shadow.records if x.action==action)
    return certification_identity("V28_QUALIFICATION_SEMANTIC_OUTPUT",dict(action=action,pipeline_status=certification.architecture.status,delivery_status=certification.delivery.status,certification_status=certification.status,shadow_records=records))


@dataclass(frozen=True)
class RuntimeSample:
    health:RuntimeHealthSnapshot;runtime_sequence:int;heartbeat_at:str;observed_at:str
    health_status:str;source_identity:str;environment_identity:str;policy_reference:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if type(self.health) is not RuntimeHealthSnapshot or self.health.replay_identity!=identity("V28_RUNTIME_HEALTH_SNAPSHOT_REPLAY",self.health.canonical_payload()):raise ValueError("RUNTIME_SAMPLE_HEALTH_INVALID")
        if self.runtime_sequence!=self.health.runtime_sequence_id or self.health_status not in {"HEALTHY","UNHEALTHY"} or (self.health_status=="HEALTHY")!=self.health.healthy:raise ValueError("RUNTIME_SAMPLE_STATUS_INVALID")
        if not self.source_identity or self.source_identity!=self.health.source_authority or not self.environment_identity or self.policy_reference!=self.health.policy_reference:raise ValueError("RUNTIME_SAMPLE_LINEAGE_INVALID")
        heartbeat,observed=parse_utc(self.heartbeat_at),parse_utc(self.observed_at)
        if canonical_utc(self.heartbeat_at)!=canonical_utc(self.health.observed_at) or observed<heartbeat:raise ValueError("RUNTIME_SAMPLE_HEARTBEAT_INVALID")
        if self.replay_identity!=certification_identity("V28_QUALIFICATION_RUNTIME_SAMPLE",self.canonical_payload()):raise ValueError("RUNTIME_SAMPLE_REPLAY_INVALID")
def create_runtime_sample(**values:Any)->RuntimeSample:return RuntimeSample(**values,replay_identity=certification_identity("V28_QUALIFICATION_RUNTIME_SAMPLE",values))

@dataclass(frozen=True)
class RecoveryEvidence:
    status:str;source_identity:str;observed_at:str;campaign_identity:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"NONE","ATTEMPTED"} or not self.source_identity or not self.campaign_identity:raise ValueError("RECOVERY_EVIDENCE_INVALID")
        parse_utc(self.observed_at)
        if self.replay_identity!=certification_identity("V28_RECOVERY_EVIDENCE",self.canonical_payload()):raise ValueError("RECOVERY_EVIDENCE_REPLAY_INVALID")
def create_recovery_evidence(**values:Any)->RecoveryEvidence:return RecoveryEvidence(**values,replay_identity=certification_identity("V28_RECOVERY_EVIDENCE",values))

@dataclass(frozen=True)
class QualificationRun:
    ordinal:int;symbol:str;environment_identity:str;runtime_sequence:int;evaluation_time:str
    scenario:QualificationScenario;runtime_sample:RuntimeSample;publication:PublishedExecutionPlan
    pipeline:PipelineValidationReport;delivery:DeliveryValidationReport;receipt:DeliveryReceipt
    certification:CertificationReport;recovery:RecoveryEvidence;previous_run_identity:str|None
    policy_identity:str;pr265_campaign_identity:str;run_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="run_identity"}
    def __post_init__(self):
        campaign=self.certification.campaign
        reports=((self.pipeline,PipelineValidationReport,"V28_PIPELINE_VALIDATION"),(self.delivery,DeliveryValidationReport,"V28_DELIVERY_VALIDATION"),(self.certification,CertificationReport,"V28_END_TO_END_CERTIFICATION"))
        if any(not report_identity_valid(*x) for x in reports):raise ValueError("QUALIFICATION_RUN_REPORT_INTEGRITY_INVALID")
        if self.certification.architecture!=self.pipeline or self.certification.delivery!=self.delivery:raise ValueError("QUALIFICATION_RUN_DIRECT_EVIDENCE_MISMATCH")
        if self.pipeline.campaign!=campaign or self.delivery.campaign!=campaign or self.pr265_campaign_identity!=campaign.campaign_identity:raise ValueError("QUALIFICATION_RUN_PR265_CAMPAIGN_MISMATCH")
        if campaign.policy_reference!=PR265_POLICY or (self.symbol,self.environment_identity,self.runtime_sequence)!=(campaign.symbol,campaign.environment_identity,campaign.runtime_sequence_id):raise ValueError("QUALIFICATION_RUN_CAMPAIGN_FIELDS_MISMATCH")
        if canonical_utc(self.evaluation_time)!=canonical_utc(campaign.evaluation_time):raise ValueError("QUALIFICATION_RUN_EVALUATION_MISMATCH")
        normalized=normalized_projection_identity(family_identity=self.scenario.family_identity,fixture_identity=self.scenario.fixture_identity,symbol=self.symbol,environment_identity=self.environment_identity,action=self.scenario.action)
        if self.scenario.normalized_input_identity!=normalized or self.scenario.expected_semantic_output_identity!=semantic_output_identity(self.certification,self.scenario.action):raise ValueError("QUALIFICATION_RUN_SCENARIO_PROJECTION_INVALID")
        if self.runtime_sample.runtime_sequence!=self.runtime_sequence or self.runtime_sample.environment_identity!=self.environment_identity or canonical_utc(self.runtime_sample.health.evaluation_time)!=canonical_utc(self.evaluation_time):raise ValueError("QUALIFICATION_RUN_RUNTIME_MISMATCH")
        if self.publication.publication_replay_identity!=identity("V28_EXECUTION_PUBLICATION_REPLAY",self.publication.canonical_payload()) or self.publication.publication_replay_identity!=campaign.publication_replay_identity:raise ValueError("QUALIFICATION_RUN_PUBLICATION_INVALID")
        if self.receipt.replay_identity!=identity("V28_DELIVERY_RECEIPT_REPLAY",self.receipt.canonical_payload()) or self.receipt.publication_replay_identity!=self.publication.publication_replay_identity or self.receipt.environment_identity!=self.environment_identity:raise ValueError("QUALIFICATION_RUN_RECEIPT_INVALID")
        if self.recovery.campaign_identity!=campaign.campaign_identity or self.policy_identity=="":raise ValueError("QUALIFICATION_RUN_POLICY_OR_RECOVERY_INVALID")
        if self.run_identity!=certification_identity("V28_QUALIFICATION_RUN",self.canonical_payload()):raise ValueError("QUALIFICATION_RUN_IDENTITY_INVALID")
def create_qualification_run(**values:Any)->QualificationRun:return QualificationRun(**values,run_identity=certification_identity("V28_QUALIFICATION_RUN",values))

@dataclass(frozen=True)
class QualificationCampaign:
    campaign_identity:str;lineage_identity:str|None;started_at:str;expires_at:str
    symbol:str;environment_identity:str;scenario_family_identity:str;runs:tuple[QualificationRun,...]
    policy:QualificationPolicy;production_authorized:bool
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="campaign_identity"}
    def __post_init__(self):
        start,end=parse_utc(self.started_at),parse_utc(self.expires_at)
        if type(self.policy) is not QualificationPolicy or self.production_authorized is not False or (end-start).total_seconds()!=self.policy.expiry_after_seconds:raise ValueError("QUALIFICATION_CAMPAIGN_POLICY_INVALID")
        if not self.runs or tuple(x.ordinal for x in self.runs)!=tuple(range(1,len(self.runs)+1)):raise ValueError("QUALIFICATION_CAMPAIGN_SEQUENCE_INVALID")
        for run in self.runs: QualificationRun(**run.__dict__)
        if any((x.symbol,x.environment_identity,x.scenario.family_identity,x.policy_identity)!=(self.symbol,self.environment_identity,self.scenario_family_identity,self.policy.policy_identity) for x in self.runs):raise ValueError("QUALIFICATION_CAMPAIGN_CROSS_RUN_MISMATCH")
        if tuple(x.previous_run_identity for x in self.runs)!=(None,)+tuple(x.run_identity for x in self.runs[:-1]):raise ValueError("QUALIFICATION_RUN_LINEAGE_INVALID")
        if len({x.certification.replay_identity for x in self.runs})!=len(self.runs) or len({x.pr265_campaign_identity for x in self.runs})!=len(self.runs):raise ValueError("QUALIFICATION_CERTIFICATION_REUSE_INVALID")
        times=tuple(parse_utc(x.evaluation_time) for x in self.runs)
        if times!=tuple(sorted(times)) or any(t<start or t>=end for t in times):raise ValueError("QUALIFICATION_CAMPAIGN_TIME_INVALID")
        sequences=tuple(x.runtime_sequence for x in self.runs)
        if self.policy.require_strict_runtime_sequence and any(b!=a+1 for a,b in zip(sequences,sequences[1:])):raise ValueError("QUALIFICATION_CAMPAIGN_RUNTIME_SEQUENCE_INVALID")
        counts={a:sum(x.scenario.action==a for x in self.runs) for a in ACTIONS};span=(times[-1]-times[0]).total_seconds()
        density=(len(self.runs)-1)/(span/3600) if span>0 else 0
        if len(self.runs)<self.policy.minimum_run_count or any(v<self.policy.minimum_runs_per_action for v in counts.values()) or span<self.policy.minimum_campaign_duration_seconds or density<self.policy.minimum_evidence_density_per_hour:raise ValueError("QUALIFICATION_CAMPAIGN_LONG_DURATION_INSUFFICIENT")
        if self.campaign_identity!=certification_identity("V28_QUALIFICATION_CAMPAIGN",self.canonical_payload()):raise ValueError("QUALIFICATION_CAMPAIGN_IDENTITY_INVALID")
    def is_active(self,at:str)->bool:return parse_utc(self.started_at)<=parse_utc(at)<parse_utc(self.expires_at)
    def is_expired(self,at:str)->bool:return parse_utc(at)>=parse_utc(self.expires_at)
def create_qualification_campaign(*,lineage_identity:str|None,started_at:str,symbol:str,environment_identity:str,scenario_family_identity:str,runs:Iterable[QualificationRun],policy:QualificationPolicy)->QualificationCampaign:
    start=canonical_utc(started_at);expires=canonical_utc(parse_utc(start)+timedelta(seconds=policy.expiry_after_seconds));values=dict(lineage_identity=lineage_identity,started_at=start,expires_at=expires,symbol=symbol,environment_identity=environment_identity,scenario_family_identity=scenario_family_identity,runs=tuple(runs),policy=policy,production_authorized=False)
    return QualificationCampaign(campaign_identity=certification_identity("V28_QUALIFICATION_CAMPAIGN",values),**values)
