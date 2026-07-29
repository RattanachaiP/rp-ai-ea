"""Append-only, content-addressed evaluation registry."""
from dataclasses import dataclass
from .identity import identity_for
from .models import EvaluationReport

@dataclass(frozen=True)
class EvaluationRegistry:
    reports: tuple[EvaluationReport, ...] = (); registry_identity: str = ""
    def __post_init__(self):
        reports = tuple(self.reports); object.__setattr__(self, "reports", reports)
        for report in reports: EvaluationReport(**report.__dict__)
        if len({x.candidate_identity for x in reports}) != len(reports): raise ValueError("DUPLICATE_CANDIDATE_EVALUATION")
        expected = identity_for("EVALUATION_REGISTRY", {"report_identities": tuple(x.report_identity for x in reports)})
        if self.registry_identity and self.registry_identity != expected: raise ValueError("EVALUATION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)
    def append(self, report): return EvaluationRegistry(self.reports + (report,))
