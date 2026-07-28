"""Explicit immutable campaign history with verified lineage and expiry."""
from dataclasses import dataclass
from .pipeline_validator import certification_identity
from .qualification_campaign import PR266_POLICY, QualificationCampaign

@dataclass(frozen=True)
class QualificationRegistry:
    campaigns:tuple[QualificationCampaign,...]=()
    policy_reference:str=PR266_POLICY
    def __post_init__(self):
        if self.policy_reference!=PR266_POLICY:raise ValueError("QUALIFICATION_REGISTRY_POLICY_INVALID")
        seen=set();previous=None
        for campaign in self.campaigns:
            if type(campaign) is not QualificationCampaign or campaign.campaign_identity in seen:raise ValueError("QUALIFICATION_REGISTRY_CORRUPT")
            if campaign.lineage_identity!=previous:raise ValueError("QUALIFICATION_CAMPAIGN_LINEAGE_INVALID")
            seen.add(campaign.campaign_identity);previous=campaign.campaign_identity
    @property
    def registry_identity(self):return certification_identity("V28_QUALIFICATION_REGISTRY",self)
    def append(self,campaign:QualificationCampaign):
        expected=self.campaigns[-1].campaign_identity if self.campaigns else None
        if type(campaign) is not QualificationCampaign or campaign.lineage_identity!=expected:raise ValueError("QUALIFICATION_CAMPAIGN_LINEAGE_INVALID")
        return QualificationRegistry(self.campaigns+(campaign,))
    def active_at(self,at:str):return tuple(x for x in self.campaigns if not x.is_expired(at))
