"""Identity-bound submission of authoritative PR266 evidence for human review."""
from dataclasses import dataclass
import re

from .campaign_statistics import CampaignStatistics
from .execution_plan import parse_utc
from .pipeline_validator import certification_identity
from .qualification_policy import POLICY_VERSION as QUALIFICATION_VERSION
from .qualification_registry import QualificationRegistry
from .qualification_report import QualificationReport
from .production_readiness_policy import ProductionReadinessPolicy


@dataclass(frozen=True)
class RepositoryEvidence:
    """Attestation from a governed repository observer, not a caller-supplied SHA."""
    commit_sha: str
    repository_identity: str
    source_authority: str
    observed_at: str
    evidence_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "evidence_identity"}

    def __post_init__(self):
        parse_utc(self.observed_at)
        if (not re.fullmatch(r"[0-9a-f]{40}", self.commit_sha) or not self.repository_identity or
                not self.source_authority.startswith("GOVERNED_REPOSITORY_OBSERVER:")):
            raise ValueError("READINESS_REPOSITORY_EVIDENCE_INVALID")
        if self.evidence_identity != certification_identity("V28_REPOSITORY_EVIDENCE", self.canonical_payload()):
            raise ValueError("READINESS_REPOSITORY_EVIDENCE_IDENTITY_INVALID")


def create_repository_evidence(**values) -> RepositoryEvidence:
    return RepositoryEvidence(**values, evidence_identity=certification_identity("V28_REPOSITORY_EVIDENCE", values))


@dataclass(frozen=True)
class ProductionReadinessCandidate:
    qualification_registry: QualificationRegistry
    qualification_report: QualificationReport
    campaign_statistics: CampaignStatistics
    policy: ProductionReadinessPolicy
    architecture_version: str
    repository_evidence: RepositoryEvidence
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
        RepositoryEvidence(**self.repository_evidence.__dict__)
        if self.generation < 1 or (self.generation == 1) != (self.previous_candidate_identity is None):
            raise ValueError("READINESS_CANDIDATE_GENERATION_INVALID")
        if (self.architecture_version != self.policy.required_architecture_version or
                self.policy.required_qualification_version != QUALIFICATION_VERSION):
            raise ValueError("READINESS_CANDIDATE_VERSION_MISMATCH")
        registry, report, stats = self.qualification_registry, self.qualification_report, self.campaign_statistics
        if (report.policy_identity != registry.policy.policy_identity or
                report.campaign_identity != registry.campaigns[-1].campaign_identity or
                stats.registry_identity != registry.registry_identity or
                stats.policy_identity != registry.policy.policy_identity or
                stats.campaign_identities != tuple(c.campaign_identity for c in registry.campaigns) or
                report.campaign_summary != stats):
            raise ValueError("READINESS_CANDIDATE_QUALIFICATION_MISMATCH")
        # PR266 owns qualification semantics. PR267 consumes its result; it does not redefine PASS.
        if report.operational_recommendation not in {"NOT READY", "CONDITIONALLY READY", "READY FOR HUMAN REVIEW"}:
            raise ValueError("READINESS_CANDIDATE_QUALIFICATION_SEMANTICS_INVALID")
        if self.candidate_identity != certification_identity("V28_PRODUCTION_READINESS_CANDIDATE", self.canonical_payload()):
            raise ValueError("READINESS_CANDIDATE_IDENTITY_INVALID")


def create_production_readiness_candidate(**values) -> ProductionReadinessCandidate:
    return ProductionReadinessCandidate(
        **values, candidate_identity=certification_identity("V28_PRODUCTION_READINESS_CANDIDATE", values))
