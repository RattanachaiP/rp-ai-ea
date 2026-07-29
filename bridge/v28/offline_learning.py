"""Offline-only transformation of Outcome Evidence into Learning Evidence.

This boundary deliberately accepts an :class:`OutcomeRegistry`, rather than a
collection of trades.  It has no broker, runtime, strategy, training, tuning,
or production-decision dependency or authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .outcome_contract import OutcomeRecord
from .outcome_evidence import OutcomeEvidenceContract, replay_validate as validate_outcome_evidence
from .outcome_registry import OutcomeRegistry
from .pipeline_validator import certification_identity

DATASET_SCHEMA_VERSION = "V28.LEARNING_DATASET.1.0"
LEARNING_EVIDENCE_VERSION = "V28.LEARNING_EVIDENCE.1.0"
LEARNING_REGISTRY_VERSION = "V28.LEARNING_REGISTRY.1.0"
CREATION_POLICY = "V28_OFFLINE_LEARNING_POLICY@1.0.0"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class LearningFeatureSet:
    """Features copied from immutable pre-result Outcome snapshots."""
    market_context: Mapping[str, Any]
    regime: Mapping[str, Any]
    opportunity: Mapping[str, Any]
    decision_context: Mapping[str, Any]
    confidence: float
    risk_context: Mapping[str, Any]
    execution_facts: Mapping[str, Any]
    feature_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "feature_identity"}

    def __post_init__(self):
        for name in ("market_context", "regime", "opportunity", "decision_context",
                     "risk_context", "execution_facts"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise ValueError("LEARNING_FEATURES_INVALID")
            object.__setattr__(self, name, _freeze(value))
        if type(self.confidence) not in (int, float) or not 0 <= self.confidence <= 1:
            raise ValueError("LEARNING_FEATURES_INVALID")
        if self.feature_identity != certification_identity("V28_LEARNING_FEATURES", self.canonical_payload()):
            raise ValueError("LEARNING_FEATURE_IDENTITY_INVALID")


@dataclass(frozen=True)
class LearningLabel:
    """Observed result label; descriptive evidence, never a recommendation."""
    trade_result: Mapping[str, Any]
    expectancy_evidence: Mapping[str, Any]
    holding_time_seconds: float
    exit_reason: str
    slippage: float
    spread: float
    commission: float
    label_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "label_identity"}

    def __post_init__(self):
        object.__setattr__(self, "trade_result", _freeze(self.trade_result))
        object.__setattr__(self, "expectancy_evidence", _freeze(self.expectancy_evidence))
        if not isinstance(self.trade_result, Mapping) or not isinstance(self.expectancy_evidence, Mapping):
            raise ValueError("LEARNING_LABEL_INVALID")
        if not self.exit_reason or any(type(v) not in (int, float) for v in (
                self.holding_time_seconds, self.slippage, self.spread, self.commission)):
            raise ValueError("LEARNING_LABEL_INVALID")
        if self.label_identity != certification_identity("V28_LEARNING_LABEL", self.canonical_payload()):
            raise ValueError("LEARNING_LABEL_IDENTITY_INVALID")


@dataclass(frozen=True)
class LearningExample:
    outcome_identity: str
    trade_identity: str
    features: LearningFeatureSet
    label: LearningLabel
    example_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "example_identity"}

    def __post_init__(self):
        LearningFeatureSet(**self.features.__dict__); LearningLabel(**self.label.__dict__)
        if not self.outcome_identity or not self.trade_identity:
            raise ValueError("LEARNING_EXAMPLE_INVALID")
        if self.example_identity != certification_identity("V28_LEARNING_EXAMPLE", self.canonical_payload()):
            raise ValueError("LEARNING_EXAMPLE_IDENTITY_INVALID")


def _normalise(record: OutcomeRecord) -> LearningExample:
    """Pure projection. Callers cannot use this to bypass the registry boundary."""
    OutcomeRecord(**record.__dict__)
    execution = record.execution_facts.canonical_payload()
    features_values = dict(
        market_context=record.runtime_snapshot.captured_payload,
        regime=record.market_regime_snapshot.captured_payload,
        opportunity=record.opportunity_snapshot.captured_payload,
        decision_context=record.decision_snapshot.captured_payload,
        confidence=record.confidence,
        risk_context=record.risk_snapshot.captured_payload,
        execution_facts=execution,
    )
    features = LearningFeatureSet(**features_values, feature_identity=certification_identity(
        "V28_LEARNING_FEATURES", features_values))
    result = record.result.canonical_payload()
    label_values = dict(
        trade_result=result,
        expectancy_evidence={"net_profit": record.result.net_profit,
                             "initial_risk": record.result.initial_risk,
                             "r_multiple": record.result.r_multiple},
        holding_time_seconds=record.result.holding_time_seconds,
        exit_reason=record.lifecycle.exit.exit_reason,
        slippage=record.slippage, spread=record.spread,
        commission=record.result.commission,
    )
    label = LearningLabel(**label_values, label_identity=certification_identity("V28_LEARNING_LABEL", label_values))
    values = dict(outcome_identity=record.outcome_identity, trade_identity=record.trade_identity,
                  features=features, label=label)
    return LearningExample(**values, example_identity=certification_identity("V28_LEARNING_EXAMPLE", values))


@dataclass(frozen=True)
class LearningDataset:
    examples: tuple[LearningExample, ...]
    source_outcome_registry_identity: str
    source_outcome_evidence_identity: str
    dataset_version_identity: str
    creation_policy: str
    dataset_identity: str
    schema_version: str = DATASET_SCHEMA_VERSION

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "dataset_identity"}

    def __post_init__(self):
        if self.schema_version != DATASET_SCHEMA_VERSION or self.creation_policy != CREATION_POLICY:
            raise ValueError("LEARNING_DATASET_VERSION_INVALID")
        identities = []
        for example in self.examples:
            LearningExample(**example.__dict__); identities.append(example.outcome_identity)
        if len(identities) != len(set(identities)):
            raise ValueError("LEARNING_DATASET_DUPLICATE_OUTCOME")
        version_values = {"schema_version": self.schema_version, "creation_policy": self.creation_policy,
                          "source_outcome_registry_identity": self.source_outcome_registry_identity}
        if self.dataset_version_identity != certification_identity("V28_LEARNING_DATASET_VERSION", version_values):
            raise ValueError("LEARNING_DATASET_VERSION_IDENTITY_INVALID")
        if self.dataset_identity != certification_identity("V28_LEARNING_DATASET", self.canonical_payload()):
            raise ValueError("LEARNING_DATASET_IDENTITY_INVALID")


def build_learning_dataset(registry: OutcomeRegistry,
                           evidence: OutcomeEvidenceContract) -> LearningDataset:
    """Build deterministically from the sole authoritative Outcome boundary."""
    OutcomeRegistry(**registry.__dict__); OutcomeEvidenceContract(**evidence.__dict__)
    if not validate_outcome_evidence(registry, evidence):
        raise ValueError("LEARNING_SOURCE_OUTCOME_EVIDENCE_INVALID")
    examples = tuple(_normalise(record) for record in registry.expectancy_dataset)
    version_values = {"schema_version": DATASET_SCHEMA_VERSION, "creation_policy": CREATION_POLICY,
                      "source_outcome_registry_identity": registry.registry_identity}
    values = dict(examples=examples, source_outcome_registry_identity=registry.registry_identity,
                  source_outcome_evidence_identity=evidence.replay_identity,
                  dataset_version_identity=certification_identity("V28_LEARNING_DATASET_VERSION", version_values),
                  creation_policy=CREATION_POLICY, schema_version=DATASET_SCHEMA_VERSION)
    return LearningDataset(**values, dataset_identity=certification_identity("V28_LEARNING_DATASET", values))


def validate_dataset_replay(registry: OutcomeRegistry, evidence: OutcomeEvidenceContract,
                            dataset: LearningDataset) -> bool:
    try:
        LearningDataset(**dataset.__dict__)
        return build_learning_dataset(registry, evidence) == dataset
    except (TypeError, ValueError, AttributeError):
        return False


@dataclass(frozen=True)
class LearningSnapshot:
    dataset_identity: str
    dataset_version_identity: str
    example_identities: tuple[str, ...]
    record_count: int
    snapshot_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "snapshot_identity"}

    def __post_init__(self):
        if self.record_count != len(self.example_identities):
            raise ValueError("LEARNING_SNAPSHOT_COUNT_INVALID")
        if self.snapshot_identity != certification_identity("V28_LEARNING_SNAPSHOT", self.canonical_payload()):
            raise ValueError("LEARNING_SNAPSHOT_IDENTITY_INVALID")


@dataclass(frozen=True)
class LearningEvidenceContract:
    dataset: LearningDataset
    snapshot: LearningSnapshot
    source_authority: str
    integrity_validated: bool
    replay_validated: bool
    training_performed: bool
    production_authorized: bool
    evidence_identity: str
    schema_version: str = LEARNING_EVIDENCE_VERSION

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "evidence_identity"}

    def __post_init__(self):
        LearningDataset(**self.dataset.__dict__); LearningSnapshot(**self.snapshot.__dict__)
        if (self.schema_version != LEARNING_EVIDENCE_VERSION or self.source_authority != "OUTCOME_REGISTRY_ONLY" or
                self.integrity_validated is not True or self.replay_validated is not True or
                self.training_performed is not False or self.production_authorized is not False or
                self.snapshot.dataset_identity != self.dataset.dataset_identity):
            raise ValueError("LEARNING_EVIDENCE_CONTRACT_INVALID")
        if self.evidence_identity != certification_identity("V28_LEARNING_EVIDENCE", self.canonical_payload()):
            raise ValueError("LEARNING_EVIDENCE_IDENTITY_INVALID")


def publish_learning_evidence(registry: OutcomeRegistry, outcome_evidence: OutcomeEvidenceContract,
                              dataset: LearningDataset) -> LearningEvidenceContract:
    if not validate_dataset_replay(registry, outcome_evidence, dataset):
        raise ValueError("LEARNING_DATASET_REPLAY_INVALID")
    snapshot_values = dict(dataset_identity=dataset.dataset_identity,
                           dataset_version_identity=dataset.dataset_version_identity,
                           example_identities=tuple(x.example_identity for x in dataset.examples),
                           record_count=len(dataset.examples))
    snapshot = LearningSnapshot(**snapshot_values, snapshot_identity=certification_identity(
        "V28_LEARNING_SNAPSHOT", snapshot_values))
    values = dict(dataset=dataset, snapshot=snapshot, source_authority="OUTCOME_REGISTRY_ONLY",
                  integrity_validated=True, replay_validated=True, training_performed=False,
                  production_authorized=False, schema_version=LEARNING_EVIDENCE_VERSION)
    return LearningEvidenceContract(**values, evidence_identity=certification_identity("V28_LEARNING_EVIDENCE", values))


@dataclass(frozen=True)
class LearningRegistry:
    entries: tuple[LearningEvidenceContract, ...]
    registry_identity: str
    schema_version: str = LEARNING_REGISTRY_VERSION

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "registry_identity"}

    def __post_init__(self):
        if self.schema_version != LEARNING_REGISTRY_VERSION:
            raise ValueError("LEARNING_REGISTRY_VERSION_INVALID")
        seen = set()
        for entry in self.entries:
            LearningEvidenceContract(**entry.__dict__)
            if entry.dataset.dataset_identity in seen:
                raise ValueError("LEARNING_REGISTRY_DUPLICATE_DATASET")
            seen.add(entry.dataset.dataset_identity)
        if self.registry_identity != certification_identity("V28_LEARNING_REGISTRY", self.canonical_payload()):
            raise ValueError("LEARNING_REGISTRY_IDENTITY_INVALID")

    def append(self, evidence: LearningEvidenceContract) -> "LearningRegistry":
        LearningEvidenceContract(**evidence.__dict__)
        values = {"entries": self.entries + (evidence,), "schema_version": LEARNING_REGISTRY_VERSION}
        return LearningRegistry(**values, registry_identity=certification_identity("V28_LEARNING_REGISTRY", values))


def create_learning_registry() -> LearningRegistry:
    values = {"entries": (), "schema_version": LEARNING_REGISTRY_VERSION}
    return LearningRegistry(**values, registry_identity=certification_identity("V28_LEARNING_REGISTRY", values))
