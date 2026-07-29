"""Authoritative PR266/PR267 provenance embedded in outcome evidence."""
from dataclasses import dataclass

from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate
from .production_readiness_registry import ProductionReadinessRegistry
from .production_readiness_report import ProductionReadinessReport
from .qualification_registry import QualificationRegistry
from .qualification_report import QualificationReport


@dataclass(frozen=True)
class OutcomeGovernanceEvidence:
    qualification_registry: QualificationRegistry
    qualification_report: QualificationReport
    readiness_candidate: ProductionReadinessCandidate
    readiness_registry: ProductionReadinessRegistry
    readiness_report: ProductionReadinessReport
    evidence_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "evidence_identity"}

    def __post_init__(self):
        QualificationRegistry(**self.qualification_registry.__dict__)
        QualificationReport(**self.qualification_report.__dict__)
        ProductionReadinessCandidate(**self.readiness_candidate.__dict__)
        ProductionReadinessRegistry(**self.readiness_registry.__dict__)
        ProductionReadinessReport(**self.readiness_report.__dict__)
        candidate, report = self.readiness_candidate, self.readiness_report
        if (candidate.qualification_registry != self.qualification_registry or
                candidate.qualification_report != self.qualification_report or
                not self.readiness_registry.candidates or self.readiness_registry.candidates[-1] != candidate or
                report.candidate_identity != candidate.candidate_identity or
                report.readiness_registry_identity != self.readiness_registry.registry_identity or
                report.qualification_registry_identity != self.qualification_registry.registry_identity or
                report.qualification_report_identity != self.qualification_report.replay_identity):
            raise ValueError("OUTCOME_GOVERNANCE_LINEAGE_INVALID")
        if self.evidence_identity != certification_identity("V28_OUTCOME_GOVERNANCE_EVIDENCE", self.canonical_payload()):
            raise ValueError("OUTCOME_GOVERNANCE_EVIDENCE_IDENTITY_INVALID")


def create_outcome_governance_evidence(**values) -> OutcomeGovernanceEvidence:
    return OutcomeGovernanceEvidence(
        **values, evidence_identity=certification_identity("V28_OUTCOME_GOVERNANCE_EVIDENCE", values))
