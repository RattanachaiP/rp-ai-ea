"""Immutable contracts for independent candidate-model evaluation (PR272)."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping
from learning.common.immutable import freeze, thaw
from .identity import identity_for

EVALUATION_SCHEMA_VERSION = "PR272.EVALUATION.1.0"
DIMENSIONS = ("predictive_performance", "generalization", "stability", "calibration",
              "risk_characteristics", "replay_consistency", "dataset_coverage",
              "confidence_reliability", "regime_robustness")

def _text(value): return isinstance(value, str) and bool(value.strip())
def _number(value): return type(value) in (int, float) and isfinite(value)

@dataclass(frozen=True)
class EvaluationPolicy:
    policy_identity: str
    minimum_records: int = 2
    maximum_mse: float = 1.0
    minimum_score: float = .5
    holdout_modulus: int = 5
    schema_version: str = EVALUATION_SCHEMA_VERSION
    def __post_init__(self):
        if (not _text(self.policy_identity) or type(self.minimum_records) is not int or self.minimum_records < 1
                or not _number(self.maximum_mse) or self.maximum_mse <= 0 or not _number(self.minimum_score)
                or not 0 <= self.minimum_score <= 1 or type(self.holdout_modulus) is not int
                or self.holdout_modulus < 2 or self.schema_version != EVALUATION_SCHEMA_VERSION):
            raise ValueError("EVALUATION_POLICY_INVALID")

@dataclass(frozen=True)
class DimensionResult:
    dimension: str; score: float; passed: bool; evidence: Mapping[str, object]
    def __post_init__(self):
        if self.dimension not in DIMENSIONS or not _number(self.score) or not 0 <= self.score <= 1 or type(self.passed) is not bool:
            raise ValueError("EVALUATION_DIMENSION_INVALID")
        object.__setattr__(self, "score", float(self.score)); object.__setattr__(self, "evidence", freeze(dict(self.evidence)))

@dataclass(frozen=True)
class StatisticalValidation:
    record_count: int; mean_error: float; mean_absolute_error: float; mean_squared_error: float; error_stddev: float
    def __post_init__(self):
        if type(self.record_count) is not int or self.record_count < 1 or any(not _number(getattr(self, n)) for n in self.__dataclass_fields__):
            raise ValueError("STATISTICAL_VALIDATION_INVALID")

@dataclass(frozen=True)
class ReplayValidation:
    input_digest: str; report_digest: str; consistent: bool = True
    def __post_init__(self):
        if not _text(self.input_digest) or not _text(self.report_digest) or self.consistent is not True:
            raise ValueError("REPLAY_VALIDATION_INVALID")

@dataclass(frozen=True)
class EvaluationReport:
    candidate_identity: str; candidate_registry_identity: str; training_evidence_identity: str
    learning_registry_identity: str; analytics_identity: str; policy_identity: str
    dimensions: tuple[DimensionResult, ...]; candidate_score: float; qualified: bool
    qualification_reasons: tuple[str, ...]; statistical_validation: StatisticalValidation
    replay_validation: ReplayValidation; report_identity: str = ""; schema_version: str = EVALUATION_SCHEMA_VERSION
    advisory_only: bool = True; runtime_authorized: bool = False; deployment_authorized: bool = False
    promotion_authorized: bool = False; production_authorized: bool = False
    def __post_init__(self):
        dims = tuple(self.dimensions); reasons = tuple(self.qualification_reasons)
        if (not all(_text(getattr(self, n)) for n in ("candidate_identity", "candidate_registry_identity",
                "training_evidence_identity", "learning_registry_identity", "analytics_identity", "policy_identity"))
                or tuple(x.dimension for x in dims) != DIMENSIONS or not _number(self.candidate_score)
                or abs(self.candidate_score - sum(x.score for x in dims) / len(DIMENSIONS)) > 1e-12
                or type(self.qualified) is not bool or not reasons or not all(_text(x) for x in reasons)
                or self.schema_version != EVALUATION_SCHEMA_VERSION or self.advisory_only is not True
                or any((self.runtime_authorized, self.deployment_authorized, self.promotion_authorized, self.production_authorized))):
            raise ValueError("EVALUATION_REPORT_INVALID")
        for x in dims: DimensionResult(x.dimension, x.score, x.passed, thaw(x.evidence))
        StatisticalValidation(**self.statistical_validation.__dict__); ReplayValidation(**self.replay_validation.__dict__)
        object.__setattr__(self, "dimensions", dims); object.__setattr__(self, "qualification_reasons", reasons)
        expected = identity_for("EVALUATION_REPORT", self.canonical_payload())
        if self.report_identity and self.report_identity != expected: raise ValueError("EVALUATION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self, "report_identity", expected)
    def canonical_payload(self):
        return {"candidate_identity": self.candidate_identity, "candidate_registry_identity": self.candidate_registry_identity,
          "training_evidence_identity": self.training_evidence_identity, "learning_registry_identity": self.learning_registry_identity,
          "analytics_identity": self.analytics_identity, "policy_identity": self.policy_identity,
          "dimensions": tuple({"dimension": x.dimension, "score": x.score, "passed": x.passed, "evidence": thaw(x.evidence)} for x in self.dimensions),
          "candidate_score": self.candidate_score, "qualified": self.qualified, "qualification_reasons": self.qualification_reasons,
          "statistical_validation": self.statistical_validation.__dict__, "replay_validation": self.replay_validation.__dict__,
          "schema_version": self.schema_version, "advisory_only": self.advisory_only,
          "runtime_authorized": self.runtime_authorized, "deployment_authorized": self.deployment_authorized,
          "promotion_authorized": self.promotion_authorized, "production_authorized": self.production_authorized}
