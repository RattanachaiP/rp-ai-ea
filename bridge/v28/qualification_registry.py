"""Serialized immutable registry versions proving append-only campaign lineage."""
from dataclasses import dataclass
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .qualification_campaign import QualificationCampaign
from .qualification_policy import QualificationPolicy
@dataclass(frozen=True)
class RegistryAppend:
    generation:int;previous_registry_identity:str;campaign_identity:str;appended_at:str
    policy_identity:str;operation_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="operation_identity"}
    def __post_init__(self):
        parse_utc(self.appended_at)
        if self.generation<1 or not all((self.previous_registry_identity,self.campaign_identity,self.policy_identity)):raise ValueError("REGISTRY_APPEND_INVALID")
        if self.operation_identity!=certification_identity("V28_QUALIFICATION_REGISTRY_APPEND",self.canonical_payload()):raise ValueError("REGISTRY_APPEND_IDENTITY_INVALID")
@dataclass(frozen=True)
class QualificationRegistry:
    generation:int;previous_registry_identity:str|None;campaigns:tuple[QualificationCampaign,...]
    append_operation:RegistryAppend|None;policy:QualificationPolicy;registry_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="registry_identity"}
    def __post_init__(self):
        if self.generation!=len(self.campaigns):raise ValueError("QUALIFICATION_REGISTRY_GENERATION_INVALID")
        if self.generation==0:
            if self.previous_registry_identity is not None or self.append_operation is not None:raise ValueError("QUALIFICATION_REGISTRY_ROOT_INVALID")
        else:
            op=self.append_operation
            if type(op) is not RegistryAppend or op.generation!=self.generation or op.previous_registry_identity!=self.previous_registry_identity or op.campaign_identity!=self.campaigns[-1].campaign_identity or op.policy_identity!=self.policy.policy_identity:raise ValueError("QUALIFICATION_REGISTRY_PREDECESSOR_INVALID")
        seen=set();previous=None;prior_end=None
        for campaign in self.campaigns:
            if campaign.policy.policy_identity!=self.policy.policy_identity or campaign.campaign_identity in seen or campaign.lineage_identity!=previous:raise ValueError("QUALIFICATION_REGISTRY_CAMPAIGN_LINEAGE_INVALID")
            if prior_end is not None and parse_utc(campaign.started_at)<prior_end:raise ValueError("QUALIFICATION_REGISTRY_PERIOD_OVERLAP")
            seen.add(campaign.campaign_identity);previous=campaign.campaign_identity;prior_end=parse_utc(campaign.expires_at)
        if self.registry_identity!=certification_identity("V28_QUALIFICATION_REGISTRY",self.canonical_payload()):raise ValueError("QUALIFICATION_REGISTRY_IDENTITY_INVALID")
    def append(self,campaign:QualificationCampaign,*,appended_at:str):
        expected=self.campaigns[-1].campaign_identity if self.campaigns else None
        if campaign.lineage_identity!=expected or campaign.policy.policy_identity!=self.policy.policy_identity:raise ValueError("QUALIFICATION_CAMPAIGN_LINEAGE_INVALID")
        values=dict(generation=self.generation+1,previous_registry_identity=self.registry_identity,campaign_identity=campaign.campaign_identity,appended_at=appended_at,policy_identity=self.policy.policy_identity)
        op=RegistryAppend(**values,operation_identity=certification_identity("V28_QUALIFICATION_REGISTRY_APPEND",values))
        registry_values=dict(generation=self.generation+1,previous_registry_identity=self.registry_identity,campaigns=self.campaigns+(campaign,),append_operation=op,policy=self.policy)
        return QualificationRegistry(**registry_values,registry_identity=certification_identity("V28_QUALIFICATION_REGISTRY",registry_values))
    def active_at(self,at:str):return tuple(x for x in self.campaigns if x.is_active(at))
def create_registry(policy:QualificationPolicy)->QualificationRegistry:
    values=dict(generation=0,previous_registry_identity=None,campaigns=(),append_operation=None,policy=policy)
    return QualificationRegistry(**values,registry_identity=certification_identity("V28_QUALIFICATION_REGISTRY",values))
