"""Immutable, identity-bound contracts for governed offline training (PR271)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any, Mapping

from learning.common.immutable import freeze, thaw
from .identity import identity_for

TRAINING_SCHEMA_VERSION = "PR271.TRAINING.1.0"
ALLOWED_SOURCE_TYPES = frozenset({"LEARNING_REGISTRY", "LEARNING_EVIDENCE", "OUTCOME_ANALYTICS"})


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _verify(kind: str, value: object, payload: Mapping[str, Any]) -> None:
    if value != identity_for(kind, payload):
        raise ValueError(f"{kind}_IDENTITY_INVALID")


@dataclass(frozen=True)
class TrainingSource:
    source_type: str
    source_identity: str
    source_version: str
    records: tuple[Mapping[str, Any], ...]
    source_digest: str = ""

    def __post_init__(self) -> None:
        if self.source_type not in ALLOWED_SOURCE_TYPES or not _text(self.source_identity) or not _text(self.source_version):
            raise ValueError("TRAINING_SOURCE_INVALID")
        frozen = tuple(freeze(dict(row)) for row in self.records)
        object.__setattr__(self, "records", frozen)
        payload = self.canonical_payload()
        expected = identity_for("TRAINING_SOURCE", payload)
        if self.source_digest and self.source_digest != expected:
            raise ValueError("TRAINING_SOURCE_DIGEST_INVALID")
        object.__setattr__(self, "source_digest", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {"source_type": self.source_type, "source_identity": self.source_identity,
                "source_version": self.source_version, "records": thaw(self.records)}


@dataclass(frozen=True)
class TrainingDataset:
    sources: tuple[TrainingSource, ...]
    rows: tuple[Mapping[str, Any], ...]
    dataset_version: str
    dataset_identity: str = ""

    def __post_init__(self) -> None:
        if not self.sources or not _text(self.dataset_version):
            raise ValueError("TRAINING_DATASET_INVALID")
        kinds = tuple(source.source_type for source in self.sources)
        if len(kinds) != len(set(kinds)) or any(kind not in ALLOWED_SOURCE_TYPES for kind in kinds):
            raise ValueError("TRAINING_SOURCE_SET_INVALID")
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "rows", tuple(freeze(dict(row)) for row in self.rows))
        payload = self.canonical_payload()
        expected = identity_for("TRAINING_DATASET", payload)
        if self.dataset_identity and self.dataset_identity != expected:
            raise ValueError("TRAINING_DATASET_IDENTITY_INVALID")
        object.__setattr__(self, "dataset_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {"sources": [s.source_digest for s in self.sources], "rows": thaw(self.rows),
                "dataset_version": self.dataset_version}


@dataclass(frozen=True)
class TrainingConfiguration:
    feature_fields: tuple[str, ...]
    label_field: str
    algorithm: str
    algorithm_parameters: Mapping[str, Any] = field(default_factory=dict)
    random_seed: int = 0
    policy_identity: str = ""
    code_version: str = ""
    schema_version: str = TRAINING_SCHEMA_VERSION
    configuration_identity: str = ""

    def __post_init__(self) -> None:
        fields = tuple(self.feature_fields)
        if (not fields or len(fields) != len(set(fields)) or not all(_text(x) for x in fields)
                or not _text(self.label_field) or self.label_field in fields or not _text(self.algorithm)
                or not isinstance(self.random_seed, int) or isinstance(self.random_seed, bool)
                or not _text(self.policy_identity) or not _text(self.code_version)
                or self.schema_version != TRAINING_SCHEMA_VERSION):
            raise ValueError("TRAINING_CONFIGURATION_INVALID")
        object.__setattr__(self, "feature_fields", fields)
        object.__setattr__(self, "algorithm_parameters", freeze(dict(self.algorithm_parameters)))
        payload = self.canonical_payload()
        expected = identity_for("TRAINING_CONFIGURATION", payload)
        if self.configuration_identity and self.configuration_identity != expected:
            raise ValueError("TRAINING_CONFIGURATION_IDENTITY_INVALID")
        object.__setattr__(self, "configuration_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {"feature_fields": self.feature_fields, "label_field": self.label_field,
                "algorithm": self.algorithm, "algorithm_parameters": thaw(self.algorithm_parameters),
                "random_seed": self.random_seed, "policy_identity": self.policy_identity,
                "code_version": self.code_version, "schema_version": self.schema_version}


@dataclass(frozen=True)
class FeatureMatrix:
    feature_names: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    labels: tuple[float, ...]
    source_dataset_identity: str
    pipeline_identity: str = ""

    def __post_init__(self) -> None:
        names, values, labels = tuple(self.feature_names), tuple(tuple(row) for row in self.values), tuple(self.labels)
        if (not names or len(values) != len(labels) or not values
                or any(len(row) != len(names) for row in values)
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x)
                       for row in values for x in row)
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) for x in labels)):
            raise ValueError("FEATURE_MATRIX_INVALID")
        object.__setattr__(self, "feature_names", names)
        object.__setattr__(self, "values", tuple(tuple(float(x) for x in row) for row in values))
        object.__setattr__(self, "labels", tuple(float(x) for x in labels))
        payload = self.canonical_payload(); expected = identity_for("FEATURE_PIPELINE", payload)
        if self.pipeline_identity and self.pipeline_identity != expected:
            raise ValueError("FEATURE_PIPELINE_IDENTITY_INVALID")
        object.__setattr__(self, "pipeline_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {"feature_names": self.feature_names, "values": self.values, "labels": self.labels,
                "source_dataset_identity": self.source_dataset_identity}


@dataclass(frozen=True)
class TrainingLineage:
    dataset_identity: str
    source_digests: tuple[str, ...]
    configuration_identity: str
    pipeline_identity: str
    parent_candidate_identities: tuple[str, ...] = ()
    lineage_identity: str = ""

    def __post_init__(self) -> None:
        if not all(_text(x) for x in (self.dataset_identity, self.configuration_identity, self.pipeline_identity)):
            raise ValueError("TRAINING_LINEAGE_INVALID")
        for name in ("source_digests", "parent_candidate_identities"):
            values = tuple(getattr(self, name))
            if len(values) != len(set(values)) or not all(_text(x) for x in values):
                raise ValueError("TRAINING_LINEAGE_INVALID")
            object.__setattr__(self, name, values)
        payload = self.canonical_payload(); expected = identity_for("TRAINING_LINEAGE", payload)
        if self.lineage_identity and self.lineage_identity != expected: raise ValueError("TRAINING_LINEAGE_IDENTITY_INVALID")
        object.__setattr__(self, "lineage_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "lineage_identity"}


@dataclass(frozen=True)
class ModelMetadata:
    algorithm: str
    algorithm_parameters: Mapping[str, Any]
    feature_names: tuple[str, ...]
    training_record_count: int
    metrics: Mapping[str, float]
    schema_version: str = TRAINING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (not _text(self.algorithm) or not self.feature_names or self.training_record_count < 1
                or any(not _text(k) or isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
                       for k, v in self.metrics.items())):
            raise ValueError("MODEL_METADATA_INVALID")
        object.__setattr__(self, "algorithm_parameters", freeze(dict(self.algorithm_parameters)))
        object.__setattr__(self, "feature_names", tuple(self.feature_names))
        object.__setattr__(self, "metrics", freeze({k: float(v) for k, v in self.metrics.items()}))


@dataclass(frozen=True)
class CandidateModel:
    model_artifact: Mapping[str, Any]
    metadata: ModelMetadata
    lineage: TrainingLineage
    model_identity: str = ""
    candidate_only: bool = True
    production_authorized: bool = False
    runtime_compatible: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_only or self.production_authorized or self.runtime_compatible:
            raise ValueError("CANDIDATE_AUTHORITY_INVALID")
        object.__setattr__(self, "model_artifact", freeze(dict(self.model_artifact)))
        payload = self.canonical_payload(); expected = identity_for("CANDIDATE_MODEL", payload)
        if self.model_identity and self.model_identity != expected: raise ValueError("CANDIDATE_MODEL_IDENTITY_INVALID")
        object.__setattr__(self, "model_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        metadata = {"algorithm": self.metadata.algorithm,
                    "algorithm_parameters": thaw(self.metadata.algorithm_parameters),
                    "feature_names": self.metadata.feature_names,
                    "training_record_count": self.metadata.training_record_count,
                    "metrics": thaw(self.metadata.metrics),
                    "schema_version": self.metadata.schema_version}
        return {"model_artifact": thaw(self.model_artifact), "metadata": metadata,
                "lineage_identity": self.lineage.lineage_identity, "candidate_only": self.candidate_only,
                "production_authorized": self.production_authorized, "runtime_compatible": self.runtime_compatible}


@dataclass(frozen=True)
class TrainingEvidence:
    session_identity: str
    candidate_identity: str
    lineage_identity: str
    replay_digest: str
    policy_identity: str
    status: str = "COMPLETED"
    output_type: str = "CANDIDATE_MODEL_ONLY"
    evidence_identity: str = ""

    def __post_init__(self) -> None:
        if self.status != "COMPLETED" or self.output_type != "CANDIDATE_MODEL_ONLY":
            raise ValueError("TRAINING_EVIDENCE_INVALID")
        payload = self.canonical_payload(); expected = identity_for("TRAINING_EVIDENCE", payload)
        if self.evidence_identity and self.evidence_identity != expected: raise ValueError("TRAINING_EVIDENCE_IDENTITY_INVALID")
        object.__setattr__(self, "evidence_identity", expected)

    def canonical_payload(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "evidence_identity"}


@dataclass(frozen=True)
class TrainingResult:
    candidate: CandidateModel
    evidence: TrainingEvidence
