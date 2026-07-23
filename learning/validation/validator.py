"""Deterministic statistical validation for discovered candidate patterns."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from typing import Any
from learning.pattern.candidate import CandidatePattern
from .confidence_interval import proportion_confidence_interval
from .consistency import coefficient_of_variation, consistency_score, stability_score
from .outlier import mark_outliers
from .sample_size import DEFAULT_MINIMUM_SAMPLES, validate_sample_size
from .schema import ValidationResult
from .verifier import promote, VerifiedKnowledge
from .repository import ValidationRepository

class StatisticalValidator:
    def __init__(self, repository: ValidationRepository | None = None, *, minimum_samples: int = DEFAULT_MINIMUM_SAMPLES,
                 minimum_stability: float = 0.50, maximum_win_rate_ci_width: float = 0.50) -> None:
        if minimum_samples < 1: raise ValueError("MINIMUM_SAMPLES_MUST_BE_POSITIVE")
        self.repository = repository or ValidationRepository(); self.minimum_samples = minimum_samples
        self.minimum_stability, self.maximum_win_rate_ci_width = minimum_stability, maximum_win_rate_ci_width
    @staticmethod
    def _number(record: Mapping[str, object], keys: tuple[str, ...]) -> float | None:
        source: Mapping[str, object] = record
        outcomes = record.get("outcomes")
        sources = (source, outcomes) if isinstance(outcomes, Mapping) else (source,)
        for item in sources:
            for key in keys:
                try:
                    value = float(item[key])
                    if value == value and value not in (float("inf"), float("-inf")): return value
                except (KeyError, TypeError, ValueError): pass
        return None
    def validate_pattern(self, pattern: CandidatePattern, records: Iterable[Mapping[str, object]] = ()) -> ValidationResult:
        rows = list(records); stats = pattern.statistics; samples = int(stats["samples"])
        wins = int(stats["wins"]); ci = proportion_confidence_interval(wins, samples); ci_width = ci[1] - ci[0]
        marked = mark_outliers(rows) if rows else []
        profits = [self._number(row, ("net_profit", "profit", "pnl", "realized_profit")) for row in rows]
        holdings = [self._number(row, ("holding_time", "holding", "duration", "duration_seconds")) for row in rows]
        maes = [self._number(row, ("mae",)) for row in rows]; mfes = [self._number(row, ("mfe",)) for row in rows]
        clean = lambda values: [value for value in values if value is not None]
        if rows:
            profit_stability = stability_score(clean(profits)); loss_stability = stability_score([-value for value in clean(profits) if value < 0])
            mae_stability, mfe_stability, holding_stability = stability_score(clean(maes)), stability_score(clean(mfes)), stability_score(clean(holdings))
        else:
            # Discovery stores aggregates.  Preserve the ability to validate them
            # without inventing observations; unavailable dimensions are neutral.
            average_profit = float(stats["avg_profit"])
            profit_stability = 1.0 / (1.0 + (float(stats["stddev_profit"]) / abs(average_profit) if average_profit else 0.0))
            loss_stability = mae_stability = mfe_stability = holding_stability = 1.0
        score = consistency_score((profit_stability,), (loss_stability,), (holding_stability,))
        checks = {
            "minimum_sample_size": validate_sample_size(samples, self.minimum_samples),
            "win_rate_stability": ci_width <= self.maximum_win_rate_ci_width,
            "profit_stability": profit_stability >= self.minimum_stability,
            "loss_stability": loss_stability >= self.minimum_stability,
            "mae_stability": mae_stability >= self.minimum_stability,
            "mfe_stability": mfe_stability >= self.minimum_stability,
            "holding_time_stability": holding_stability >= self.minimum_stability,
            "consistency": score >= self.minimum_stability,
        }
        if not checks["minimum_sample_size"]: status = "INSUFFICIENT_DATA"
        elif all(checks.values()): status = "VERIFIED"
        else: status = "REJECTED"
        result = ValidationResult(pattern.pattern_uuid, status, checks, {
            "samples": samples, "win_rate_confidence_interval": ci, "win_rate_ci_width": ci_width,
            "profit_cv": coefficient_of_variation(clean(profits)) if rows else (1 - profit_stability) / profit_stability,
            "profit_stability": profit_stability, "loss_stability": loss_stability, "mae_stability": mae_stability,
            "mfe_stability": mfe_stability, "holding_stability": holding_stability, "consistency_score": score,
        }, sum(any(flags.values()) for row in marked for flags in [row["outliers"]]))
        self.repository.save_result(result)
        if status == "VERIFIED": self.repository.save_knowledge(promote(pattern, result))
        return result
    def validate(self, pattern: CandidatePattern, records: Iterable[Mapping[str, object]] = ()) -> ValidationResult:
        return self.validate_pattern(pattern, records)
    def validate_incremental(self, patterns: Iterable[CandidatePattern], records_by_pattern: Mapping[str, Iterable[Mapping[str, object]]] | None = None) -> list[ValidationResult]:
        return [self.validate_pattern(pattern, (records_by_pattern or {}).get(pattern.pattern_uuid, ())) for pattern in patterns]

def validate_pattern(pattern: CandidatePattern, records: Iterable[Mapping[str, object]] = (), **kwargs: Any) -> ValidationResult:
    return StatisticalValidator(**kwargs).validate_pattern(pattern, records)
def validate(pattern: CandidatePattern, records: Iterable[Mapping[str, object]] = (), **kwargs: Any) -> ValidationResult:
    return validate_pattern(pattern, records, **kwargs)
def validate_incremental(patterns: Iterable[CandidatePattern], records_by_pattern: Mapping[str, Iterable[Mapping[str, object]]] | None = None, **kwargs: Any) -> list[ValidationResult]:
    return StatisticalValidator(**kwargs).validate_incremental(patterns, records_by_pattern)
