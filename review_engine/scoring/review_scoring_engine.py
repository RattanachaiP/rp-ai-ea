"""Pure, deterministic completed-trade review scoring."""
from __future__ import annotations
from typing import Mapping

class ReviewScoringEngine:
    METRICS = ("direction_accuracy", "entry_timing", "exit_timing", "risk_quality", "execution_quality", "confidence_calibration", "capital_efficiency", "overall_score")
    def score(self, snapshot: Mapping[str, object]) -> dict[str, float]:
        outcome = snapshot.get("outcome", {}) if isinstance(snapshot.get("outcome"), Mapping) else {}
        execution = snapshot.get("execution_context", {}) if isinstance(snapshot.get("execution_context"), Mapping) else {}
        decision = snapshot.get("decision_context", {}) if isinstance(snapshot.get("decision_context"), Mapping) else {}
        quality = snapshot.get("data_quality", {}) if isinstance(snapshot.get("data_quality"), Mapping) else {}
        rr = self._number(outcome.get("r_multiple")); profit = self._number(outcome.get("net_profit"))
        mae, mfe = abs(self._number(outcome.get("mae_points"))), abs(self._number(outcome.get("mfe_points")))
        slippage, spread = abs(self._number(execution.get("slippage_points"))), abs(self._number(execution.get("spread_points_at_entry")))
        confidence = self._number(decision.get("confidence")); completeness = self._number(quality.get("completeness_ratio"), 1.0)
        direction = 100.0 if profit > 0 else 50.0 if profit == 0 else 0.0
        entry = self._clamp(100.0 - 10.0 * slippage - 2.0 * spread)
        exit_score = self._clamp(50.0 + 50.0 * min(1.0, max(-1.0, rr)))
        risk = self._clamp(100.0 * (mfe / (mfe + mae))) if mfe + mae else 50.0
        execution_score = self._clamp(100.0 - 10.0 * slippage)
        normalized_confidence = confidence * 100.0 if confidence <= 1 else confidence
        calibration = self._clamp(100.0 - abs(normalized_confidence - direction))
        capital = self._clamp(50.0 + 50.0 * min(1.0, max(-1.0, rr)))
        values = (direction, entry, exit_score, risk, execution_score, calibration, capital)
        result = dict(zip(self.METRICS[:-1], (round(value, 6) for value in values)))
        result["overall_score"] = round(sum(values) / len(values) * self._clamp(completeness), 6)
        return result
    @staticmethod
    def _number(value: object, default: float = 0.0) -> float:
        try: return float(value) if value is not None else default
        except (TypeError, ValueError): return default
    @staticmethod
    def _clamp(value: float) -> float: return max(0.0, min(100.0, value))
