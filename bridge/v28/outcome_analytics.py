"""Deterministic, descriptive analytics over PR269 Learning Evidence.

The engine is deliberately downstream of the immutable learning-data boundary.
It cannot train, tune, generate candidates, publish decisions, or mutate runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable

from .offline_learning import LearningDataset, LearningEvidenceContract
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
    mean_confidence: float
    observed_win_rate: float
    absolute_error: float

    def __post_init__(self) -> None:
        for value in (self.lower_bound, self.upper_bound, self.mean_confidence,
                      self.observed_win_rate, self.absolute_error):
            _validate_number(value)
        if not (0 <= self.lower_bound < self.upper_bound <= 1) or self.count < 1:
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_INVALID")
        if not (0 <= self.mean_confidence <= 1 and 0 <= self.observed_win_rate <= 1):
            raise ValueError("OUTCOME_ANALYTICS_CALIBRATION_INVALID")


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
    source_learning_evidence_identity: str
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
        if self.expectancy != self.win_loss_distribution:
            raise ValueError("OUTCOME_ANALYTICS_SUMMARY_MISMATCH")
        if self.report_identity != _identity("REPORT", self.canonical_payload()):
            raise ValueError("OUTCOME_ANALYTICS_IDENTITY_INVALID")


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
    for index in sorted(buckets):
        values = buckets[index]
        confidence = sum(x.features.confidence for x in values) / len(values)
        win_rate = sum(x.label.trade_result["net_profit"] > 0 for x in values) / len(values)
        result.append(CalibrationBucket(index / 10, (index + 1) / 10, len(values),
                                        confidence, win_rate, abs(confidence - win_rate)))
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
    values = dict(
        source_dataset_identity=dataset.dataset_identity,
        source_learning_evidence_identity=evidence.evidence_identity,
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
