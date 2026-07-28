"""Identity-bound submission of PR266 evidence for human readiness review."""
from dataclasses import dataclass
import re

from .campaign_statistics import CampaignStatistics
from .pipeline_validator import certification_identity
from .qualification_policy import POLICY_VERSION as QUALIFICATION_VERSION
from .qualification_registry import QualificationRegistry
from .qualification_report import QualificationReport
from .production_readiness_policy import ProductionReadinessPolicy


@dataclass(frozen=True)
class ProductionReadinessCandidate:
    qualification_registry: QualificationRegistry
    qualification_report: QualificationReport
    campaign_statistics: CampaignStatistics
    policy: ProductionReadinessPolicy
    architecture_version: str
    repository_commit: str
    generation: int
    previous_candidate_identity: str | None
    candidate_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "candidate_identity"}

    def __post_init__(self):
        QualificationRegistry(**self.qualification_registry.__dict__)
        QualificationReport(**self.qualification_report.__dict__)
        CampaignStatistics(**self.campaign_statistics.__dict__)
        ProductionReadinessPolicy(**self.policy.__dict__)
        if self.generation < 1 or (self.generation == 1) != (self.previous_candidate_identity is None):
            raise ValueError("READINESS_CANDIDATE_GENERATION_INVALID")
        if not re.fullmatch(r"[0-9a-f]{7,64}", self.repository_commit):
            raise ValueError("READINESS_CANDIDATE_REPOSITORY_INVALID")
        if (self.architecture_version != self.policy.required_architecture_version or
                self.policy.required_qualification_version != QUALIFICATION_VERSION):
            raise ValueError("READINESS_CANDIDATE_VERSION_MISMATCH")
        registry = self.qualification_registry
        report = self.qualification_report
        stats = self.campaign_statistics
        if (report.policy_identity != registry.policy.policy_identity or
                report.campaign_identity not in tuple(c.campaign_identity for c in registry.campaigns) or
                stats.registry_identity != registry.registry_identity or
                stats.policy_identity != registry.policy.policy_identity or
                stats.campaign_identities != tuple(c.campaign_identity for c in registry.campaigns) or
                report.campaign_summary != stats):
            raise ValueError("READINESS_CANDIDATE_QUALIFICATION_MISMATCH")
        if self.candidate_identity != certification_identity("V28_PRODUCTION_READINESS_CANDIDATE", self.canonical_payload()):
            raise ValueError("READINESS_CANDIDATE_IDENTITY_INVALID")


def create_production_readiness_candidate(**values) -> ProductionReadinessCandidate:
    return ProductionReadinessCandidate(
        **values, candidate_identity=certification_identity("V28_PRODUCTION_READINESS_CANDIDATE", values))
