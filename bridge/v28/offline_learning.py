"""Offline-only transformation of Outcome Evidence into Learning Evidence.

This boundary deliberately accepts an :class:`OutcomeRegistry`, rather than a
collection of trades.  It has no broker, runtime, strategy, training, tuning,
or production-decision dependency or authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
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


def _finite(value: Any, *, nonnegative: bool = False) -> None:
    if type(value) not in (int, float) or not isfinite(value) or (nonnegative and value < 0):
        raise ValueError("LEARNING_NUMERIC_INVALID")


@dataclass(frozen=True)
class LearningFeatureSet:
    """Features copied from immutable pre-result Outcome snapshots."""
    outcome_identity: str
    trade_identity: str
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
        if not self.outcome_identity or not self.trade_identity:
            raise ValueError("LEARNING_FEATURE_LINEAGE_INVALID")
        for name in ("market_context", "regime", "opportunity", "decision_context",
                     "risk_context", "execution_facts"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise ValueError("LEARNING_FEATURES_INVALID")
            object.__setattr__(self, name, _freeze(value))
        _finite(self.confidence, nonnegative=True)
        if self.confidence > 1:
            raise ValueError("LEARNING_FEATURES_INVALID")
        if self.feature_identity != certification_identity("V28_LEARNING_FEATURES", self.canonical_payload()):
            raise ValueError("LEARNING_FEATURE_IDENTITY_INVALID")


@dataclass(frozen=True)
class LearningLabel:
    """Observed result label; descriptive evidence, never a recommendation."""
    outcome_identity: str
    trade_identity: str
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
        if not self.outcome_identity or not self.trade_identity:
            raise ValueError("LEARNING_LABEL_LINEAGE_INVALID")
        object.__setattr__(self, "trade_result", _freeze(self.trade_result))
        object.__setattr__(self, "expectancy_evidence", _freeze(self.expectancy_evidence))
        if not isinstance(self.trade_result, Mapping) or not isinstance(self.expectancy_evidence, Mapping):
            raise ValueError("LEARNING_LABEL_INVALID")
        if not self.exit_reason:
            raise ValueError("LEARNING_LABEL_INVALID")
        _finite(self.holding_time_seconds, nonnegative=True)
        _finite(self.slippage)
        _finite(self.spread, nonnegative=True)
        _finite(self.commission)
        result_keys = ("gross_profit", "commission", "swap", "net_profit", "initial_risk",
                       "r_multiple", "holding_time_seconds")
        if any(key not in self.trade_result for key in result_keys):
            raise ValueError("LEARNING_LABEL_INVALID")
        for key in result_keys:
            _finite(self.trade_result[key])
        for key in ("net_profit", "initial_risk", "r_multiple"):
            if key not in self.expectancy_evidence:
                raise ValueError("LEARNING_LABEL_INVALID")
            _finite(self.expectancy_evidence[key])
        if (self.holding_time_seconds != self.trade_result["holding_time_seconds"] or
                self.commission != self.trade_result["commission"] or
                any(self.expectancy_evidence[key] != self.trade_result[key]
                    for key in ("net_profit", "initial_risk", "r_multiple"))):
            raise ValueError("LEARNING_LABEL_PROJECTION_INVALID")
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
        lineage = (self.outcome_identity, self.trade_identity)
        if ((self.features.outcome_identity, self.features.trade_identity) != lineage or
                (self.label.outcome_identity, self.label.trade_identity) != lineage):
            raise ValueError("LEARNING_EXAMPLE_LINEAGE_INVALID")
        if self.example_identity != certification_identity("V28_LEARNING_EXAMPLE", self.canonical_payload()):
            raise ValueError("LEARNING_EXAMPLE_IDENTITY_INVALID")


def _normalise(record: OutcomeRecord) -> LearningExample:
    """Pure projection. Callers cannot use this to bypass the registry boundary."""
    OutcomeRecord(**record.__dict__)
    execution = record.execution_facts.canonical_payload()
    features_values = dict(
        outcome_identity=record.outcome_identity, trade_identity=record.trade_identity,
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
        outcome_identity=record.outcome_identity, trade_identity=record.trade_identity,
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
    source_outcome_identities: tuple[str, ...]
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
        if tuple(identities) != self.source_outcome_identities:
            raise ValueError("LEARNING_DATASET_SOURCE_LINEAGE_INVALID")
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
    values = dict(examples=examples,
                  source_outcome_identities=tuple(record.outcome_identity for record in registry.expectancy_dataset),
                  source_outcome_registry_identity=registry.registry_identity,
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
        if (self.record_count != len(self.example_identities) or
                len(set(self.example_identities)) != self.record_count):
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
                self.snapshot.dataset_identity != self.dataset.dataset_identity or
                self.snapshot.dataset_version_identity != self.dataset.dataset_version_identity or
                self.snapshot.example_identities != tuple(x.example_identity for x in self.dataset.examples) or
                self.snapshot.record_count != len(self.dataset.examples)):
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
class LearningRegistryEntry:
    sequence: int
    previous_entry_identity: str | None
    evidence: LearningEvidenceContract
    entry_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "entry_identity"}

    def __post_init__(self):
        LearningEvidenceContract(**self.evidence.__dict__)
        if self.sequence < 1 or (self.sequence == 1) != (self.previous_entry_identity is None):
            raise ValueError("LEARNING_REGISTRY_ENTRY_SEQUENCE_INVALID")
        if self.entry_identity != certification_identity("V28_LEARNING_REGISTRY_ENTRY", self.canonical_payload()):
            raise ValueError("LEARNING_REGISTRY_ENTRY_IDENTITY_INVALID")


def _registry_values(entries: tuple[LearningRegistryEntry, ...]) -> dict[str, Any]:
    previous = None if not entries else _registry_identity(entries[:-1])
    return {"entries": entries, "previous_registry_identity": previous,
            "schema_version": LEARNING_REGISTRY_VERSION}


def _registry_identity(entries: tuple[LearningRegistryEntry, ...]) -> str:
    return certification_identity("V28_LEARNING_REGISTRY", _registry_values(entries))


@dataclass(frozen=True)
class LearningRegistry:
    entries: tuple[LearningRegistryEntry, ...]
    previous_registry_identity: str | None
    registry_identity: str
    schema_version: str = LEARNING_REGISTRY_VERSION

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "registry_identity"}

    def __post_init__(self):
        if self.schema_version != LEARNING_REGISTRY_VERSION:
            raise ValueError("LEARNING_REGISTRY_VERSION_INVALID")
        if self.previous_registry_identity != _registry_values(self.entries)["previous_registry_identity"]:
            raise ValueError("LEARNING_REGISTRY_PREDECESSOR_INVALID")
        seen = set()
        for index, entry in enumerate(self.entries, 1):
            LearningRegistryEntry(**entry.__dict__)
            previous = None if index == 1 else self.entries[index - 2].entry_identity
            if entry.sequence != index or entry.previous_entry_identity != previous:
                raise ValueError("LEARNING_REGISTRY_LINEAGE_INVALID")
            if entry.evidence.dataset.dataset_identity in seen:
                raise ValueError("LEARNING_REGISTRY_DUPLICATE_DATASET")
            seen.add(entry.evidence.dataset.dataset_identity)
        if self.registry_identity != certification_identity("V28_LEARNING_REGISTRY", self.canonical_payload()):
            raise ValueError("LEARNING_REGISTRY_IDENTITY_INVALID")

    def append(self, evidence: LearningEvidenceContract) -> "LearningRegistry":
        LearningEvidenceContract(**evidence.__dict__)
        if evidence.dataset.dataset_identity in {x.evidence.dataset.dataset_identity for x in self.entries}:
            raise ValueError("LEARNING_REGISTRY_DUPLICATE_DATASET")
        entry_values = {"sequence": len(self.entries) + 1,
                        "previous_entry_identity": None if not self.entries else self.entries[-1].entry_identity,
                        "evidence": evidence}
        entry = LearningRegistryEntry(**entry_values, entry_identity=certification_identity(
            "V28_LEARNING_REGISTRY_ENTRY", entry_values))
        entries = self.entries + (entry,)
        values = _registry_values(entries)
        return LearningRegistry(**values, registry_identity=_registry_identity(entries))


def create_learning_registry() -> LearningRegistry:
    values = _registry_values(())
    return LearningRegistry(**values, registry_identity=_registry_identity(()))
