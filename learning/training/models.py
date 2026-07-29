"""Self-validating contracts for governed, offline-only training (PR271)."""
from __future__ import annotations
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping
from learning.common.immutable import freeze, thaw
from .identity import identity_for

TRAINING_SCHEMA_VERSION = "PR271.TRAINING.2.0"
ALGORITHM = "DETERMINISTIC_MEAN"


def _text(value: object) -> bool: return isinstance(value, str) and bool(value.strip())
def _finite(value: object) -> bool: return type(value) in (int, float) and isfinite(value)

@dataclass(frozen=True)
class TrainingRow:
    position: int
    outcome_identity: str
    example_identity: str
    feature_values: Mapping[str, float]
    label: float
    row_identity: str = ""
    def __post_init__(self):
        if (type(self.position) is not int or self.position < 0 or not _text(self.outcome_identity)
                or not _text(self.example_identity) or not self.feature_values or not _finite(self.label)
                or any(not _text(k) or not _finite(v) for k, v in self.feature_values.items())):
            raise ValueError("TRAINING_ROW_INVALID")
        object.__setattr__(self, "feature_values", freeze({k: float(v) for k, v in sorted(self.feature_values.items())}))
        object.__setattr__(self, "label", float(self.label))
        expected = identity_for("TRAINING_ROW", self.canonical_payload())
        if self.row_identity and self.row_identity != expected: raise ValueError("TRAINING_ROW_IDENTITY_INVALID")
        object.__setattr__(self, "row_identity", expected)
    def canonical_payload(self):
        return {"position": self.position, "outcome_identity": self.outcome_identity,
                "example_identity": self.example_identity, "feature_values": thaw(self.feature_values), "label": self.label}

@dataclass(frozen=True)
class TrainingDataset:
    rows: tuple[TrainingRow, ...]
    record_count: int
    source_learning_registry_identity: str
    source_learning_evidence_identity: str
    source_analytics_identity: str
    source_dataset_identity: str
    source_dataset_version_identity: str
    dataset_identity: str = ""
    schema_version: str = TRAINING_SCHEMA_VERSION
    def __post_init__(self):
        rows = tuple(self.rows); object.__setattr__(self, "rows", rows)
        if (self.schema_version != TRAINING_SCHEMA_VERSION or not rows or self.record_count != len(rows)
                or tuple(r.position for r in rows) != tuple(range(len(rows)))
                or len({r.outcome_identity for r in rows}) != len(rows)
                or len({r.example_identity for r in rows}) != len(rows)
                or len({r.row_identity for r in rows}) != len(rows)
                or not all(_text(x) for x in (self.source_learning_registry_identity,
                    self.source_learning_evidence_identity, self.source_analytics_identity,
                    self.source_dataset_identity, self.source_dataset_version_identity))):
            raise ValueError("TRAINING_DATASET_LINEAGE_INVALID")
        for row in rows: TrainingRow(**row.__dict__)
        expected = identity_for("TRAINING_DATASET", self.canonical_payload())
        if self.dataset_identity and self.dataset_identity != expected: raise ValueError("TRAINING_DATASET_IDENTITY_INVALID")
        object.__setattr__(self, "dataset_identity", expected)
    def canonical_payload(self):
        return {"row_identities": tuple(r.row_identity for r in self.rows), "record_count": self.record_count,
                "source_learning_registry_identity": self.source_learning_registry_identity,
                "source_learning_evidence_identity": self.source_learning_evidence_identity,
                "source_analytics_identity": self.source_analytics_identity,
                "source_dataset_identity": self.source_dataset_identity,
                "source_dataset_version_identity": self.source_dataset_version_identity,
                "schema_version": self.schema_version}

@dataclass(frozen=True)
class TrainingConfiguration:
    feature_fields: tuple[str, ...]
    label_field: str = "r_multiple"
    algorithm: str = ALGORITHM
    algorithm_parameters: Mapping[str, float] = field(default_factory=lambda: {"offset": 0.0})
    policy_identity: str = ""
    code_version: str = ""
    schema_version: str = TRAINING_SCHEMA_VERSION
    configuration_identity: str = ""
    def __post_init__(self):
        fields = tuple(self.feature_fields); params = dict(self.algorithm_parameters)
        if (not fields or len(fields) != len(set(fields)) or not all(_text(x) for x in fields)
                or self.label_field != "r_multiple" or self.algorithm != ALGORITHM
                or set(params) != {"offset"} or not _finite(params["offset"])
                or not _text(self.policy_identity) or not _text(self.code_version)
                or self.schema_version != TRAINING_SCHEMA_VERSION):
            raise ValueError("TRAINING_CONFIGURATION_INVALID")
        object.__setattr__(self, "feature_fields", fields); object.__setattr__(self, "algorithm_parameters", freeze({"offset": float(params["offset"])}))
        expected = identity_for("TRAINING_CONFIGURATION", self.canonical_payload())
        if self.configuration_identity and self.configuration_identity != expected: raise ValueError("TRAINING_CONFIGURATION_IDENTITY_INVALID")
        object.__setattr__(self, "configuration_identity", expected)
    def canonical_payload(self):
        return {"feature_fields": self.feature_fields, "label_field": self.label_field, "algorithm": self.algorithm,
                "algorithm_parameters": thaw(self.algorithm_parameters), "policy_identity": self.policy_identity,
                "code_version": self.code_version, "schema_version": self.schema_version}

@dataclass(frozen=True)
class FeatureMatrix:
    feature_names: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    labels: tuple[float, ...]
    row_identities: tuple[str, ...]
    source_dataset_identity: str
    pipeline_identity: str = ""
    def __post_init__(self):
        names, values, labels, ids = tuple(self.feature_names), tuple(tuple(r) for r in self.values), tuple(self.labels), tuple(self.row_identities)
        if (not names or len(names) != len(set(names)) or not all(_text(n) for n in names)
                or not values or len(values) != len(labels) or len(values) != len(ids) or len(ids) != len(set(ids))
                or any(len(r) != len(names) or any(not _finite(x) for x in r) for r in values)
                or any(not _finite(x) for x in labels) or not _text(self.source_dataset_identity)):
            raise ValueError("FEATURE_MATRIX_INVALID")
        object.__setattr__(self, "feature_names", names); object.__setattr__(self, "values", tuple(tuple(float(x) for x in r) for r in values)); object.__setattr__(self, "labels", tuple(float(x) for x in labels)); object.__setattr__(self, "row_identities", ids)
        expected = identity_for("FEATURE_MATRIX", self.canonical_payload())
        if self.pipeline_identity and self.pipeline_identity != expected: raise ValueError("FEATURE_MATRIX_IDENTITY_INVALID")
        object.__setattr__(self, "pipeline_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "pipeline_identity"}

@dataclass(frozen=True)
class TrainingLineage:
    dataset_identity: str; configuration_identity: str; pipeline_identity: str
    source_learning_registry_identity: str; source_learning_evidence_identity: str; source_analytics_identity: str
    policy_identity: str
    lineage_identity: str = ""
    def __post_init__(self):
        if not all(_text(getattr(self, k)) for k in self.__dataclass_fields__ if k != "lineage_identity"): raise ValueError("TRAINING_LINEAGE_INVALID")
        expected = identity_for("TRAINING_LINEAGE", self.canonical_payload())
        if self.lineage_identity and self.lineage_identity != expected: raise ValueError("TRAINING_LINEAGE_IDENTITY_INVALID")
        object.__setattr__(self, "lineage_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "lineage_identity"}

@dataclass(frozen=True)
class ModelMetadata:
    algorithm: str; algorithm_parameters: Mapping[str, float]; feature_names: tuple[str, ...]
    training_record_count: int; training_row_identities: tuple[str, ...]; metrics: Mapping[str, float]
    def __post_init__(self):
        params, metrics, names, ids = dict(self.algorithm_parameters), dict(self.metrics), tuple(self.feature_names), tuple(self.training_row_identities)
        if (self.algorithm != ALGORITHM or set(params) != {"offset"} or not _finite(params["offset"])
                or not names or len(names) != len(set(names)) or not all(_text(x) for x in names)
                or type(self.training_record_count) is not int or self.training_record_count < 1
                or len(ids) != self.training_record_count or len(ids) != len(set(ids)) or not all(_text(x) for x in ids)
                or set(metrics) != {"training_mse"} or not _finite(metrics["training_mse"]) or metrics["training_mse"] < 0):
            raise ValueError("MODEL_METADATA_INVALID")
        object.__setattr__(self, "algorithm_parameters", freeze({"offset": float(params["offset"])})); object.__setattr__(self, "feature_names", names); object.__setattr__(self, "training_row_identities", ids); object.__setattr__(self, "metrics", freeze({"training_mse": float(metrics["training_mse"])}))

@dataclass(frozen=True)
class CandidateModel:
    model_artifact: Mapping[str, Any]; metadata: ModelMetadata; lineage: TrainingLineage; model_identity: str = ""
    candidate_only: bool = True; runtime_authorized: bool = False; strategy_authorized: bool = False
    risk_authorized: bool = False; broker_authorized: bool = False; deployment_authorized: bool = False
    promotion_authorized: bool = False; production_authorized: bool = False
    def __post_init__(self):
        ModelMetadata(**self.metadata.__dict__); TrainingLineage(**self.lineage.__dict__)
        if self.candidate_only is not True or any((self.runtime_authorized, self.strategy_authorized, self.risk_authorized,
                self.broker_authorized, self.deployment_authorized, self.promotion_authorized, self.production_authorized)):
            raise ValueError("CANDIDATE_AUTHORITY_INVALID")
        artifact = dict(self.model_artifact)
        if (set(artifact) != {"format", "prediction"} or artifact["format"] != "PR271.DETERMINISTIC_MEAN.1.0"
                or not _finite(artifact["prediction"])): raise ValueError("CANDIDATE_ARTIFACT_INVALID")
        object.__setattr__(self, "model_artifact", freeze({"format": artifact["format"], "prediction": float(artifact["prediction"])}))
        expected = identity_for("CANDIDATE_MODEL", self.canonical_payload())
        if self.model_identity and self.model_identity != expected: raise ValueError("CANDIDATE_MODEL_IDENTITY_INVALID")
        object.__setattr__(self, "model_identity", expected)
    def canonical_payload(self):
        return {"model_artifact": thaw(self.model_artifact), "metadata": {"algorithm": self.metadata.algorithm,
            "algorithm_parameters": thaw(self.metadata.algorithm_parameters), "feature_names": self.metadata.feature_names,
            "training_record_count": self.metadata.training_record_count, "training_row_identities": self.metadata.training_row_identities,
            "metrics": thaw(self.metadata.metrics)}, "lineage_identity": self.lineage.lineage_identity,
            **{k: getattr(self, k) for k in ("candidate_only", "runtime_authorized", "strategy_authorized", "risk_authorized", "broker_authorized", "deployment_authorized", "promotion_authorized", "production_authorized")}}

@dataclass(frozen=True)
class TrainingEvidence:
    session_identity: str; candidate_identity: str; lineage_identity: str; configuration_identity: str
    policy_identity: str; replay_digest: str; evidence_identity: str = ""
    output_type: str = "CANDIDATE_MODEL_ONLY"
    def __post_init__(self):
        if self.output_type != "CANDIDATE_MODEL_ONLY" or not all(_text(getattr(self, k)) for k in self.__dataclass_fields__ if k != "evidence_identity"):
            raise ValueError("TRAINING_EVIDENCE_INVALID")
        expected = identity_for("TRAINING_EVIDENCE", self.canonical_payload())
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("TRAINING_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "evidence_identity"}

@dataclass(frozen=True)
class TrainingResult:
    candidate: CandidateModel; evidence: TrainingEvidence
    def __post_init__(self):
        CandidateModel(**self.candidate.__dict__); TrainingEvidence(**self.evidence.__dict__)
        lineage = self.candidate.lineage
        session_payload = {"configuration_identity": lineage.configuration_identity, "lineage_identity": lineage.lineage_identity,
                           "candidate_identity": self.candidate.model_identity, "policy_identity": self.evidence.policy_identity}
        if (self.evidence.candidate_identity != self.candidate.model_identity or self.evidence.lineage_identity != lineage.lineage_identity
                or self.evidence.configuration_identity != lineage.configuration_identity
                or self.evidence.policy_identity != lineage.policy_identity
                or self.evidence.session_identity != identity_for("TRAINING_SESSION", session_payload)
                or self.evidence.replay_digest != identity_for("TRAINING_REPLAY", session_payload)):
            raise ValueError("TRAINING_RESULT_BINDING_INVALID")
