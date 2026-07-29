"""Deterministic, descriptive analytics over PR269 Learning Evidence.

The engine is deliberately downstream of the immutable learning-data boundary.
It cannot train, tune, generate candidates, publish decisions, or mutate runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable

from .offline_learning import LearningDataset, LearningEvidenceContract, LearningSnapshot
from .pipeline_validator import certification_identity

ANALYTICS_SCHEMA_VERSION = "V28.OUTCOME_ANALYTICS.1.0"
ANALYTICS_POLICY = "V28_OUTCOME_ANALYTICS_POLICY@1.0.0"


def _identity(kind: str, value: object) -> str:
    return certification_identity(f"V28_ANALYTICS_{kind}", value)


def _validate_number(value: float) -> None:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("OUTCOME_ANALYTICS_NUMERIC_INVALID")


@dataclass(frozen=True)
class PerformanceSummary:
    count: int
    wins: int
    losses: int
    breakeven: int
    total_net_profit: float
    mean_net_profit: float
    total_r_multiple: float
    expectancy_r: float

    def __post_init__(self) -> None:
        if self.count < 0 or min(self.wins, self.losses, self.breakeven) < 0:
            raise ValueError("OUTCOME_ANALYTICS_COUNT_INVALID")
        if self.wins + self.losses + self.breakeven != self.count:
            raise ValueError("OUTCOME_ANALYTICS_DISTRIBUTION_INVALID")
        for value in (self.total_net_profit, self.mean_net_profit,
                      self.total_r_multiple, self.expectancy_r):
            _validate_number(value)
        expected_net = self.total_net_profit / self.count if self.count else 0.0
        expected_r = self.total_r_multiple / self.count if self.count else 0.0
        if self.mean_net_profit != expected_net or self.expectancy_r != expected_r:
            raise ValueError("OUTCOME_ANALYTICS_SUMMARY_ARITHMETIC_INVALID")


@dataclass(frozen=True)
class GroupPerformance:
    group: str
    performance: PerformanceSummary

    def __post_init__(self) -> None:
        if not self.group:
            raise ValueError("OUTCOME_ANALYTICS_GROUP_INVALID")
        PerformanceSummary(**self.performance.__dict__)


@dataclass(frozen=True)
class DrawdownAnalysis:
    maximum_net_drawdown: float
    maximum_r_drawdown: float
    ending_cumulative_net: float
    ending_cumulative_r: float

    def __post_init__(self) -> None:
        for value in self.__dict__.values():
            _validate_number(value)
        if self.maximum_net_drawdown < 0 or self.maximum_r_drawdown < 0:
            raise ValueError("OUTCOME_ANALYTICS_DRAWDOWN_INVALID")


@dataclass(frozen=True)
class CalibrationBucket:
    lower_bound: float
    upper_bound: float
    count: int
    confidence_sum: float
    observed_wins: int
    mean_confidence: float
    observed_win_rate: float
    absolute_error: float
    upper_bound_inclusive: bool

    def __post_init__(self) -> None:
        for value in (self.lower_bound, self.upper_bound, self.confidence_sum, self.mean_confidence,
                      self.observed_win_rate, self.absolute_error):
            _validate_number(value)
        if (not (0 <= self.lower_bound < self.upper_bound <= 1) or self.count < 0 or
                not 0 <= self.observed_wins <= self.count or
                type(self.upper_bound_inclusive) is not bool):
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_INVALID")
        if not (0 <= self.mean_confidence <= 1 and 0 <= self.observed_win_rate <= 1):
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_INVALID")
        expected_confidence = self.confidence_sum / self.count if self.count else 0.0
        expected_win_rate = self.observed_wins / self.count if self.count else 0.0
        if (self.mean_confidence != expected_confidence or
                self.observed_win_rate != expected_win_rate or
                self.absolute_error != abs(self.mean_confidence - self.observed_win_rate)):
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_ARITHMETIC_INVALID")


@dataclass(frozen=True)
class ErrorClass:
    classification: str
    count: int
    outcome_identities: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not self.classification or self.count < 1 or
                self.count != len(self.outcome_identities) or
                len(set(self.outcome_identities)) != self.count):
            raise ValueError("OUTCOME_ANALYTICS_ERROR_CLASS_INVALID")


@dataclass(frozen=True)
class OutcomeAnalyticsReport:
    source_dataset_identity: str
    source_dataset_version_identity: str
    source_learning_evidence_identity: str
    source_learning_snapshot: LearningSnapshot
    source_outcome_identities: tuple[str, ...]
    source_example_identities: tuple[str, ...]
    source_example_lineage: tuple[tuple[str, str], ...]
    source_record_count: int
    losing_outcome_identities: tuple[str, ...]
    expectancy: PerformanceSummary
    win_loss_distribution: PerformanceSummary
    drawdown: DrawdownAnalysis
    regime_performance: tuple[GroupPerformance, ...]
    opportunity_performance: tuple[GroupPerformance, ...]
    confidence_calibration: tuple[CalibrationBucket, ...]
    error_classification: tuple[ErrorClass, ...]
    analytics_only: bool
    training_performed: bool
    candidates_generated: bool
    runtime_mutated: bool
    production_authorized: bool
    report_identity: str
    policy_reference: str = ANALYTICS_POLICY
    schema_version: str = ANALYTICS_SCHEMA_VERSION

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "report_identity"}

    def __post_init__(self) -> None:
        LearningSnapshot(**self.source_learning_snapshot.__dict__)
        PerformanceSummary(**self.expectancy.__dict__)
        PerformanceSummary(**self.win_loss_distribution.__dict__)
        DrawdownAnalysis(**self.drawdown.__dict__)
        for item in self.regime_performance + self.opportunity_performance:
            GroupPerformance(**item.__dict__)
        for item in self.confidence_calibration:
            CalibrationBucket(**item.__dict__)
        for item in self.error_classification:
            ErrorClass(**item.__dict__)
        if (not self.source_dataset_identity or not self.source_learning_evidence_identity or
                self.policy_reference != ANALYTICS_POLICY or self.schema_version != ANALYTICS_SCHEMA_VERSION or
                self.analytics_only is not True or self.training_performed is not False or
                self.candidates_generated is not False or self.runtime_mutated is not False or
                self.production_authorized is not False):
            raise ValueError("OUTCOME_ANALYTICS_AUTHORITY_INVALID")
        snapshot = self.source_learning_snapshot
        if (self.source_dataset_identity != snapshot.dataset_identity or
                self.source_dataset_version_identity != snapshot.dataset_version_identity or
                self.source_example_identities != snapshot.example_identities or
                self.source_example_lineage != tuple(zip(self.source_outcome_identities,
                                                          self.source_example_identities)) or
                self.source_record_count != snapshot.record_count or
                self.source_record_count != len(self.source_outcome_identities) or
                len(set(self.source_outcome_identities)) != self.source_record_count or
                len(set(self.source_example_identities)) != self.source_record_count):
            raise ValueError("OUTCOME_ANALYTICS_LINEAGE_INVALID")
        if self.expectancy != self.win_loss_distribution:
            raise ValueError("OUTCOME_ANALYTICS_SUMMARY_MISMATCH")
        if self.expectancy.count != self.source_record_count:
            raise ValueError("OUTCOME_ANALYTICS_SOURCE_COUNT_INVALID")
        if (self.drawdown.ending_cumulative_net != self.expectancy.total_net_profit or
                self.drawdown.ending_cumulative_r != self.expectancy.total_r_multiple):
            raise ValueError("OUTCOME_ANALYTICS_DRAWDOWN_TOTAL_INVALID")
        self._validate_groups(self.regime_performance, "REGIME")
        self._validate_groups(self.opportunity_performance, "OPPORTUNITY")
        self._validate_calibration()
        self._validate_errors()
        if self.report_identity != _identity("REPORT", self.canonical_payload()):
            raise ValueError("OUTCOME_ANALYTICS_IDENTITY_INVALID")

    def _validate_groups(self, groups: tuple[GroupPerformance, ...], name: str) -> None:
        names = tuple(group.group for group in groups)
        if names != tuple(sorted(set(names))):
            raise ValueError(f"OUTCOME_ANALYTICS_{name}_GROUP_ORDER_INVALID")
        if sum(group.performance.count for group in groups) != self.source_record_count:
            raise ValueError(f"OUTCOME_ANALYTICS_{name}_GROUP_COUNT_INVALID")

    def _validate_calibration(self) -> None:
        previous_upper = None
        for index, bucket in enumerate(self.confidence_calibration):
            # Canonical deciles are [lower, upper), except [0.9, 1.0].
            expected_lower, expected_upper = index / 10, (index + 1) / 10
            if (bucket.lower_bound != expected_lower or bucket.upper_bound != expected_upper or
                    bucket.upper_bound_inclusive is not (index == 9) or
                    (previous_upper is not None and bucket.lower_bound != previous_upper)):
                raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_ORDER_INVALID")
            previous_upper = bucket.upper_bound
        if sum(bucket.count for bucket in self.confidence_calibration) != self.source_record_count:
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_COUNT_INVALID")

    def _validate_errors(self) -> None:
        names = tuple(error.classification for error in self.error_classification)
        if names != tuple(sorted(set(names))):
            raise ValueError("OUTCOME_ANALYTICS_ERROR_CLASS_ORDER_INVALID")
        flattened = tuple(identity for error in self.error_classification
                          for identity in error.outcome_identities)
        if (len(set(flattened)) != len(flattened) or
                set(flattened) - set(self.source_outcome_identities) or
                set(self.losing_outcome_identities) - set(self.source_outcome_identities) or
                len(set(self.losing_outcome_identities)) != len(self.losing_outcome_identities) or
                set(flattened) != set(self.losing_outcome_identities)):
            raise ValueError("OUTCOME_ANALYTICS_ERROR_LINEAGE_INVALID")
        source_order = {identity: index for index, identity in enumerate(self.source_outcome_identities)}
        if (self.losing_outcome_identities != tuple(sorted(self.losing_outcome_identities,
                                                           key=source_order.__getitem__)) or
                any(error.outcome_identities != tuple(sorted(error.outcome_identities,
                                                              key=source_order.__getitem__))
                    for error in self.error_classification)):
            raise ValueError("OUTCOME_ANALYTICS_ERROR_ORDER_INVALID")


def _summary(examples: tuple) -> PerformanceSummary:
    net = tuple(float(item.label.trade_result["net_profit"]) for item in examples)
    r_values = tuple(float(item.label.expectancy_evidence["r_multiple"]) for item in examples)
    count = len(examples)
    return PerformanceSummary(count=count, wins=sum(x > 0 for x in net),
                              losses=sum(x < 0 for x in net), breakeven=sum(x == 0 for x in net),
                              total_net_profit=sum(net), mean_net_profit=sum(net) / count if count else 0.0,
                              total_r_multiple=sum(r_values), expectancy_r=sum(r_values) / count if count else 0.0)


def _groups(dataset: LearningDataset, selector: Callable) -> tuple[GroupPerformance, ...]:
    grouped: dict[str, list] = {}
    for example in dataset.examples:
        grouped.setdefault(str(selector(example)), []).append(example)
    return tuple(GroupPerformance(name, _summary(tuple(grouped[name]))) for name in sorted(grouped))


def _drawdown(dataset: LearningDataset) -> DrawdownAnalysis:
    cumulative_net = cumulative_r = peak_net = peak_r = max_net = max_r = 0.0
    for example in dataset.examples:
        cumulative_net += float(example.label.trade_result["net_profit"])
        cumulative_r += float(example.label.expectancy_evidence["r_multiple"])
        peak_net, peak_r = max(peak_net, cumulative_net), max(peak_r, cumulative_r)
        max_net, max_r = max(max_net, peak_net - cumulative_net), max(max_r, peak_r - cumulative_r)
    return DrawdownAnalysis(max_net, max_r, cumulative_net, cumulative_r)


def _calibration(dataset: LearningDataset) -> tuple[CalibrationBucket, ...]:
    buckets: dict[int, list] = {}
    for example in dataset.examples:
        index = min(int(example.features.confidence * 10), 9)
        buckets.setdefault(index, []).append(example)
    result = []
    for index in range(10):
        values = buckets.get(index, [])
        # Empty buckets remain explicit so decile semantics and ordering are
        # unambiguous. Their descriptive rates are zero.
        if not values:
            result.append(CalibrationBucket(index / 10, (index + 1) / 10, 0,
                                            0.0, 0, 0.0, 0.0, 0.0, index == 9))
            continue
        confidence_sum = sum(x.features.confidence for x in values)
        wins = sum(x.label.trade_result["net_profit"] > 0 for x in values)
        confidence = confidence_sum / len(values)
        win_rate = wins / len(values)
        result.append(CalibrationBucket(index / 10, (index + 1) / 10, len(values),
                                        confidence_sum, wins, confidence, win_rate,
                                        abs(confidence - win_rate), index == 9))
    return tuple(result)


def _errors(dataset: LearningDataset) -> tuple[ErrorClass, ...]:
    errors: dict[str, list[str]] = {}
    for example in dataset.examples:
        if example.label.trade_result["net_profit"] >= 0:
            continue
        classification = ("STOP_LOSS" if example.label.exit_reason == "STOP_LOSS"
                          else "ADVERSE_OUTCOME")
        errors.setdefault(classification, []).append(example.outcome_identity)
    return tuple(ErrorClass(name, len(errors[name]), tuple(errors[name])) for name in sorted(errors))


def analyze_learning_evidence(evidence: LearningEvidenceContract) -> OutcomeAnalyticsReport:
    """Produce replay-safe analytics without any learning or operational authority."""
    LearningEvidenceContract(**evidence.__dict__)
    dataset = evidence.dataset
    LearningDataset(**dataset.__dict__)
    summary = _summary(dataset.examples)
    losing = tuple(example.outcome_identity for example in dataset.examples
                   if example.label.trade_result["net_profit"] < 0)
    values = dict(
        source_dataset_identity=dataset.dataset_identity,
        source_dataset_version_identity=dataset.dataset_version_identity,
        source_learning_evidence_identity=evidence.evidence_identity,
        source_learning_snapshot=evidence.snapshot,
        source_outcome_identities=dataset.source_outcome_identities,
        source_example_identities=tuple(example.example_identity for example in dataset.examples),
        source_example_lineage=tuple((example.outcome_identity, example.example_identity)
                                     for example in dataset.examples),
        source_record_count=len(dataset.examples), losing_outcome_identities=losing,
        expectancy=summary, win_loss_distribution=summary, drawdown=_drawdown(dataset),
        regime_performance=_groups(dataset, lambda x: x.features.regime.get("state", "UNKNOWN")),
        opportunity_performance=_groups(dataset, lambda x: x.features.opportunity.get("archetype", "UNKNOWN")),
        confidence_calibration=_calibration(dataset), error_classification=_errors(dataset),
        analytics_only=True, training_performed=False, candidates_generated=False,
        runtime_mutated=False, production_authorized=False,
        policy_reference=ANALYTICS_POLICY, schema_version=ANALYTICS_SCHEMA_VERSION)
    return OutcomeAnalyticsReport(**values, report_identity=_identity("REPORT", values))


def validate_analytics_replay(evidence: LearningEvidenceContract, report: OutcomeAnalyticsReport) -> bool:
    try:
        OutcomeAnalyticsReport(**report.__dict__)
        return analyze_learning_evidence(evidence) == report
    except (TypeError, ValueError, AttributeError):
        return False
