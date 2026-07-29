"""Immutable, self-validating contracts for independent evaluation (PR272)."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import isclose, isfinite, sqrt
from typing import Mapping
from learning.common.immutable import freeze, thaw
from .identity import identity_for

EVALUATION_SCHEMA_VERSION = "PR272.EVALUATION.2.0"
DIMENSIONS = ("predictive_performance", "generalization", "stability", "calibration",
              "risk_characteristics", "replay_consistency", "dataset_coverage",
              "confidence_reliability", "regime_robustness")

def _text(value): return isinstance(value, str) and bool(value.strip())
def _number(value): return type(value) in (int, float) and isfinite(value)
def _close(left, right): return isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)

@dataclass(frozen=True)
class EvaluationPolicy:
    policy_reference: str
    minimum_records: int = 30
    minimum_regime_records: int = 5
    maximum_mse: float = 1.0
    minimum_dimension_score: float = .5
    maximum_confidence_brier_score: float = .25
    schema_version: str = EVALUATION_SCHEMA_VERSION
    policy_identity: str = ""
    def __post_init__(self):
        if (not _text(self.policy_reference) or type(self.minimum_records) is not int or self.minimum_records < 30
                or type(self.minimum_regime_records) is not int or self.minimum_regime_records < 2
                or self.minimum_regime_records > self.minimum_records or not _number(self.maximum_mse)
                or self.maximum_mse <= 0 or not _number(self.minimum_dimension_score)
                or not 0 <= self.minimum_dimension_score <= 1 or not _number(self.maximum_confidence_brier_score)
                or not 0 < self.maximum_confidence_brier_score <= 1 or self.schema_version != EVALUATION_SCHEMA_VERSION):
            raise ValueError("EVALUATION_POLICY_INVALID")
        expected = identity_for("EVALUATION_POLICY", self.canonical_payload())
        if self.policy_identity and self.policy_identity != expected: raise ValueError("EVALUATION_POLICY_IDENTITY_INVALID")
        object.__setattr__(self, "policy_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "policy_identity"}

@dataclass(frozen=True)
class EvaluationRow:
    position: int; outcome_identity: str; example_identity: str; label: float
    confidence: float; regime_identity: str; source_row_identity: str; row_identity: str = ""
    def __post_init__(self):
        if (type(self.position) is not int or self.position < 0 or not all(_text(getattr(self, x)) for x in
                ("outcome_identity", "example_identity", "regime_identity", "source_row_identity"))
                or not _number(self.label) or not _number(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError("EVALUATION_ROW_INVALID")
        expected = identity_for("EVALUATION_ROW", self.canonical_payload())
        if self.row_identity and self.row_identity != expected: raise ValueError("EVALUATION_ROW_IDENTITY_INVALID")
        object.__setattr__(self, "label", float(self.label)); object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "row_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "row_identity"}

@dataclass(frozen=True)
class DatasetNonOverlapProof:
    training_row_identities: tuple[str, ...]; training_example_identities: tuple[str, ...]
    evaluation_source_row_identities: tuple[str, ...]
    overlap_count: int; proof_identity: str = ""
    def __post_init__(self):
        training, examples, evaluation = tuple(self.training_row_identities), tuple(self.training_example_identities), tuple(self.evaluation_source_row_identities)
        if (not training or not examples or not evaluation or len(training) != len(examples)
                or any(len(set(x)) != len(x) for x in (training, examples, evaluation))
                or not all(_text(x) for x in training + examples + evaluation) or type(self.overlap_count) is not int
                or self.overlap_count != len(set(examples) & set(evaluation)) or self.overlap_count != 0):
            raise ValueError("EVALUATION_DATASET_OVERLAP_INVALID")
        object.__setattr__(self, "training_row_identities", training); object.__setattr__(self, "training_example_identities", examples)
        object.__setattr__(self, "evaluation_source_row_identities", evaluation)
        expected = identity_for("DATASET_NON_OVERLAP_PROOF", self.canonical_payload())
        if self.proof_identity and self.proof_identity != expected: raise ValueError("NON_OVERLAP_PROOF_IDENTITY_INVALID")
        object.__setattr__(self, "proof_identity", expected)
    def canonical_payload(self): return {"training_row_identities": self.training_row_identities,
        "training_example_identities": self.training_example_identities,
        "evaluation_source_row_identities": self.evaluation_source_row_identities, "overlap_count": self.overlap_count}

@dataclass(frozen=True)
class EvaluationDataset:
    rows: tuple[EvaluationRow, ...]; source_learning_registry_identity: str
    source_learning_evidence_identity: str; source_analytics_identity: str
    source_dataset_identity: str; source_dataset_version_identity: str
    non_overlap_proof: DatasetNonOverlapProof; dataset_identity: str = ""
    dataset_version: str = EVALUATION_SCHEMA_VERSION
    def __post_init__(self):
        rows = tuple(self.rows); object.__setattr__(self, "rows", rows)
        if (not rows or tuple(x.position for x in rows) != tuple(range(len(rows)))
                or len({x.row_identity for x in rows}) != len(rows)
                or len({x.source_row_identity for x in rows}) != len(rows)
                or len({x.outcome_identity for x in rows}) != len(rows)
                or not all(_text(getattr(self, x)) for x in ("source_learning_registry_identity",
                    "source_learning_evidence_identity", "source_analytics_identity", "source_dataset_identity",
                    "source_dataset_version_identity")) or self.dataset_version != EVALUATION_SCHEMA_VERSION):
            raise ValueError("EVALUATION_DATASET_INVALID")
        for row in rows: EvaluationRow(**row.__dict__)
        DatasetNonOverlapProof(**self.non_overlap_proof.__dict__)
        if tuple(x.source_row_identity for x in rows) != self.non_overlap_proof.evaluation_source_row_identities:
            raise ValueError("EVALUATION_DATASET_PROOF_BINDING_INVALID")
        expected = identity_for("EVALUATION_DATASET", self.canonical_payload())
        if self.dataset_identity and self.dataset_identity != expected: raise ValueError("EVALUATION_DATASET_IDENTITY_INVALID")
        object.__setattr__(self, "dataset_identity", expected)
    def canonical_payload(self): return {"row_identities": tuple(x.row_identity for x in self.rows),
        "source_learning_registry_identity": self.source_learning_registry_identity,
        "source_learning_evidence_identity": self.source_learning_evidence_identity,
        "source_analytics_identity": self.source_analytics_identity, "source_dataset_identity": self.source_dataset_identity,
        "source_dataset_version_identity": self.source_dataset_version_identity,
        "non_overlap_proof_identity": self.non_overlap_proof.proof_identity, "dataset_version": self.dataset_version}

@dataclass(frozen=True)
class DimensionResult:
    dimension: str; score: float; policy_threshold: float; passed: bool; evidence: Mapping[str, object]
    def __post_init__(self):
        if (self.dimension not in DIMENSIONS or not _number(self.score) or not 0 <= self.score <= 1
                or not _number(self.policy_threshold) or not 0 <= self.policy_threshold <= 1
                or type(self.passed) is not bool or self.passed != (self.score >= self.policy_threshold)):
            raise ValueError("EVALUATION_DIMENSION_INVALID")
        object.__setattr__(self, "score", float(self.score)); object.__setattr__(self, "evidence", freeze(dict(self.evidence)))

@dataclass(frozen=True)
class StatisticalValidation:
    record_count: int; error_sum: float; squared_error_sum: float; mean_error: float
    mean_absolute_error: float; mean_squared_error: float; error_stddev: float
    confidence_brier_score: float; regime_counts: Mapping[str, int]
    def __post_init__(self):
        regimes = dict(self.regime_counts)
        if (type(self.record_count) is not int or self.record_count < 1
                or any(not _number(getattr(self, n)) for n in self.__dataclass_fields__ if n != "regime_counts")
                or self.squared_error_sum < 0 or self.mean_absolute_error < 0 or self.mean_squared_error < 0
                or self.error_stddev < 0 or not 0 <= self.confidence_brier_score <= 1
                or not regimes or any(not _text(k) or type(v) is not int or v < 1 for k, v in regimes.items())
                or sum(regimes.values()) != self.record_count or not _close(self.mean_error, self.error_sum/self.record_count)
                or not _close(self.mean_squared_error, self.squared_error_sum/self.record_count)
                or self.mean_absolute_error**2 > self.mean_squared_error + 1e-12
                or not _close(self.error_stddev**2, self.mean_squared_error-self.mean_error**2)):
            raise ValueError("STATISTICAL_VALIDATION_INVALID")
        object.__setattr__(self, "regime_counts", freeze(dict(sorted(regimes.items()))))

@dataclass(frozen=True)
class ReplayValidation:
    first_computation_digest: str; second_computation_digest: str; consistent: bool
    def __post_init__(self):
        if (not _text(self.first_computation_digest) or not _text(self.second_computation_digest)
                or type(self.consistent) is not bool or self.consistent != (self.first_computation_digest == self.second_computation_digest)):
            raise ValueError("REPLAY_VALIDATION_INVALID")

def qualification(policy, stats, dimensions):
    reasons = []
    if stats.record_count < policy.minimum_records: reasons.append("INSUFFICIENT_EVALUATION_RECORDS")
    if any(v < policy.minimum_regime_records for v in stats.regime_counts.values()): reasons.append("INSUFFICIENT_REGIME_COVERAGE")
    reasons.extend("DIMENSION_FAILED:" + x.dimension.upper() for x in dimensions if not x.passed)
    return not reasons, tuple(reasons or ("ALL_QUALIFICATION_RULES_PASSED",))

@dataclass(frozen=True)
class EvaluationReport:
    candidate_identity: str; candidate_registry_identity: str; training_evidence_identity: str
    training_learning_registry_identity: str; training_analytics_identity: str; training_dataset_identity: str
    evaluation_dataset_identity: str; evaluation_dataset_version: str; policy: EvaluationPolicy
    dimensions: tuple[DimensionResult, ...]; candidate_score: float; qualified: bool
    qualification_reasons: tuple[str, ...]; statistical_validation: StatisticalValidation
    replay_validation: ReplayValidation; report_identity: str = ""; schema_version: str = EVALUATION_SCHEMA_VERSION
    advisory_only: bool = True; runtime_authorized: bool = False; strategy_authorized: bool = False
    risk_authorized: bool = False; broker_authorized: bool = False; deployment_authorized: bool = False
    promotion_authorized: bool = False; production_authorized: bool = False
    def __post_init__(self):
        dims, reasons = tuple(self.dimensions), tuple(self.qualification_reasons)
        EvaluationPolicy(**self.policy.__dict__); StatisticalValidation(**self.statistical_validation.__dict__)
        ReplayValidation(**self.replay_validation.__dict__)
        if (not all(_text(getattr(self, n)) for n in ("candidate_identity", "candidate_registry_identity",
                "training_evidence_identity", "training_learning_registry_identity", "training_analytics_identity",
                "training_dataset_identity", "evaluation_dataset_identity", "evaluation_dataset_version"))
                or tuple(x.dimension for x in dims) != DIMENSIONS or any(x.policy_threshold != self.policy.minimum_dimension_score for x in dims)
                or not _number(self.candidate_score) or not _close(self.candidate_score, sum(x.score for x in dims)/len(dims))
                or (self.qualified, reasons) != qualification(self.policy, self.statistical_validation, dims)
                or self.schema_version != EVALUATION_SCHEMA_VERSION or self.advisory_only is not True
                or any((self.runtime_authorized, self.strategy_authorized, self.risk_authorized, self.broker_authorized,
                        self.deployment_authorized, self.promotion_authorized, self.production_authorized))):
            raise ValueError("EVALUATION_REPORT_INVALID")
        for x in dims: DimensionResult(x.dimension, x.score, x.policy_threshold, x.passed, thaw(x.evidence))
        object.__setattr__(self, "dimensions", dims); object.__setattr__(self, "qualification_reasons", reasons)
        expected = identity_for("EVALUATION_REPORT", self.canonical_payload())
        if self.report_identity and self.report_identity != expected: raise ValueError("EVALUATION_REPORT_IDENTITY_INVALID")
        object.__setattr__(self, "report_identity", expected)
    def canonical_payload(self):
        return {k: (v.canonical_payload() | {"policy_identity": v.policy_identity} if k == "policy" else
                    tuple({"dimension": x.dimension, "score": x.score, "policy_threshold": x.policy_threshold,
                           "passed": x.passed, "evidence": thaw(x.evidence)} for x in v) if k == "dimensions" else
                    thaw(v.__dict__) if k in ("statistical_validation", "replay_validation") else v)
                for k, v in self.__dict__.items() if k != "report_identity"}
