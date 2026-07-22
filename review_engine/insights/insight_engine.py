"""Deterministic, read-only executive intelligence built from Knowledge."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable


class InsightEngine:
    """Transforms a Knowledge document only; it has no trading-layer imports."""

    SCHEMA_VERSION = "4.0.0"
    PRODUCER = "RAIP Insight Generator"
    OWNER = "RAIP Insight Layer"

    def __init__(self, *, clock: Callable[[], datetime] | None = None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(self, knowledge: Mapping[str, object]) -> dict[str, object]:
        statistics = knowledge.get("statistics", {})
        if not isinstance(statistics, Mapping):
            raise ValueError("INVALID_KNOWLEDGE_STATISTICS")
        knowledge_version = str(knowledge.get("pattern_repository_version", ""))
        if len(knowledge_version) != 64:
            raise ValueError("INVALID_KNOWLEDGE_VERSION")
        rankings = self._rank_patterns(statistics.get("pattern_statistics", {}))
        sessions = self._sessions(statistics.get("session_statistics", {}))
        states = self._states(statistics.get("market_state_statistics", {}))
        confidence = self._confidence(statistics.get("confidence_calibration", {}))
        metrics = {"pattern_ranking": rankings, "session_intelligence": sessions,
                   "market_state_intelligence": states, "confidence_intelligence": confidence,
                   "evidence_coverage": knowledge.get("generated_from", {}).get("evidence_count", 0)
                   if isinstance(knowledge.get("generated_from"), Mapping) else 0,
                   "knowledge_coverage": self._coverage(statistics)}
        summary = {"executive_summary": self._executive(metrics),
                   "best_performing_pattern": self._name(rankings["by_profit_factor"], False),
                   "worst_performing_pattern": self._name(rankings["by_profit_factor"], True),
                   "best_session": self._name(sessions["ranking"], False), "worst_session": self._name(sessions["ranking"], True),
                   "best_market_state": self._name(states["ranking"], False), "worst_market_state": self._name(states["ranking"], True),
                   "highest_confidence_zone": confidence["best_confidence_zone"], "lowest_confidence_zone": confidence["worst_confidence_zone"],
                   "pattern_stability": rankings["stability"]}
        insight_version = self._digest({"knowledge_version": knowledge_version, "metrics": metrics, "summary": summary})
        return {"schema_version": self.SCHEMA_VERSION, "producer": self.PRODUCER, "owner": self.OWNER,
                "created_at": self._iso(self.clock()), "knowledge_version": knowledge_version,
                "insight_version": insight_version, "summary": summary, "metrics": metrics,
                # Preserve the existing, immutable upstream lineage so downstream
                # advisory layers never need to inspect trading/runtime data.
                "lineage": self._lineage(knowledge, knowledge_version)}

    @staticmethod
    def _lineage(knowledge, knowledge_version):
        generated = knowledge.get("generated_from", {}) if isinstance(knowledge.get("generated_from"), Mapping) else {}
        records = generated.get("evidence_lineage", [])
        if not isinstance(records, list): records = []
        return {"knowledge_ids": [knowledge_version], "evidence": sorted(
            [{"evidence_id": str(row.get("evidence_id", "")), "snapshot_id": str(row.get("snapshot_id", ""))}
             for row in records if isinstance(row, Mapping)], key=lambda row: (row["evidence_id"], row["snapshot_id"]))}

    def _rank_patterns(self, source: object) -> dict[str, object]:
        rows = self._rows(source, ("profit_factor", "average_rr", "win_rate"))
        if isinstance(source, Mapping):
            for row in rows:
                values = source.get(row["name"], {})
                if row["profit_factor"] is None and isinstance(values, Mapping):
                    profit, loss = self._number(values.get("average_profit")), self._number(values.get("average_loss"))
                    row["profit_factor"] = self._round(profit / abs(loss)) if profit is not None and loss not in (None, 0) else None
        # Ties and unbounded all-win samples are resolved deterministically by average RR.
        return {"by_profit_factor": self._sort(rows, "profit_factor"), "by_average_rr": self._sort(rows, "average_rr"),
                "by_win_rate": self._sort(rows, "win_rate"), "stability": self._stability(rows)}

    def _sessions(self, source: object) -> dict[str, object]:
        rows = self._rows(source, ("win_rate", "profit_factor", "average_rr", "average_drawdown", "trade_count"))
        for row in rows:
            row["average_holding_time"] = row.pop("average_duration", None)
        return {"sessions": rows, "ranking": self._sort(rows, "profit_factor")}

    def _states(self, source: object) -> dict[str, object]:
        rows = self._rows(source, ("win_rate", "average_rr"))
        for row in rows:
            distribution = row.pop("confidence_distribution", {})
            row["performance"] = row["average_rr"]
            row["profitability"] = row["average_rr"]
            row["stability"] = row["win_rate"]
            row["confidence_accuracy"] = row["win_rate"]
            row["confidence_distribution"] = distribution
        return {"market_states": rows, "ranking": self._sort(rows, "performance")}

    def _confidence(self, source: object) -> dict[str, object]:
        rows = []
        if isinstance(source, Mapping):
            for zone in sorted(source):
                item = source[zone] if isinstance(source[zone], Mapping) else {}
                actual = self._number(item.get("actual_win_rate"))
                midpoint = self._midpoint(zone)
                rows.append({"zone": zone, "sample_size": int(item.get("sample_size", 0) or 0), "actual_win_rate": actual,
                             "average_rr": self._number(item.get("average_rr")), "calibration_drift": self._round(actual - midpoint) if actual is not None else None})
        eligible = [row for row in rows if row["sample_size"]]
        best = max(eligible, key=lambda row: (self._none_low(row["actual_win_rate"]), row["zone"]), default=None)
        worst = min(eligible, key=lambda row: (self._none_high(row["actual_win_rate"]), row["zone"]), default=None)
        over = [row["zone"] for row in eligible if row["calibration_drift"] is not None and row["calibration_drift"] < 0]
        under = [row["zone"] for row in eligible if row["calibration_drift"] is not None and row["calibration_drift"] > 0]
        drift = self._average([abs(row["calibration_drift"]) for row in eligible if row["calibration_drift"] is not None])
        return {"zones": rows, "overconfident_regions": over, "underconfident_regions": under,
                "best_confidence_zone": best["zone"] if best else None, "worst_confidence_zone": worst["zone"] if worst else None,
                "calibration_drift": drift}

    def _rows(self, source: object, metrics: tuple[str, ...]) -> list[dict[str, object]]:
        if not isinstance(source, Mapping): return []
        rows = []
        for name in sorted(source):
            values = source[name] if isinstance(source[name], Mapping) else {}
            row = {"name": name, "trade_count": int(values.get("trade_count", 0) or 0)}
            for metric in metrics: row[metric] = self._number(values.get(metric))
            row["average_holding_time"] = self._number(values.get("average_duration"))
            row["drawdown"] = self._number(values.get("average_drawdown"))
            rows.append(row)
        return rows

    def _sort(self, rows, metric):
        # Average RR makes undefined factors (all-win/all-loss small samples) deterministic.
        def value(row):
            metric_value = row.get(metric)
            if metric == "profit_factor" and metric_value is None and self._none_low(row.get("average_rr")) > 0:
                return float("inf")
            return self._none_low(metric_value)
        return sorted((dict(row) for row in rows), key=lambda row: (-value(row), -self._none_low(row.get("average_rr")), str(row.get("name", ""))))
    def _stability(self, rows):
        populated = [row for row in rows if row["trade_count"]]
        values = [row["win_rate"] for row in populated if row["win_rate"] is not None]
        return {"observed_patterns": len(populated), "win_rate_range": self._round(max(values) - min(values)) if values else None}
    def _coverage(self, stats):
        return {"pattern_categories": sum(bool(v.get("trade_count", 0)) for v in stats.get("pattern_statistics", {}).values()) if isinstance(stats.get("pattern_statistics"), Mapping) else 0,
                "session_categories": sum(bool(v.get("trade_count", 0)) for v in stats.get("session_statistics", {}).values()) if isinstance(stats.get("session_statistics"), Mapping) else 0,
                "market_state_categories": sum(bool(v.get("win_rate") is not None) for v in stats.get("market_state_statistics", {}).values()) if isinstance(stats.get("market_state_statistics"), Mapping) else 0}
    @staticmethod
    def _name(rows, last):
        populated = [row for row in rows if row.get("trade_count", 0) or row.get("win_rate") is not None]
        return (populated[-1] if last else populated[0]).get("name") if populated else None
    def _executive(self, metrics):
        return {"evidence_count": metrics["evidence_coverage"], "observed_patterns": metrics["pattern_ranking"]["stability"]["observed_patterns"], "calibration_drift": metrics["confidence_intelligence"]["calibration_drift"]}
    @staticmethod
    def _number(value):
        try: return round(float(value), 6) if value is not None else None
        except (TypeError, ValueError): return None
    @staticmethod
    def _none_low(value): return float("-inf") if value is None else value
    @staticmethod
    def _none_high(value): return float("inf") if value is None else value
    @staticmethod
    def _average(values): return round(sum(values) / len(values), 6) if values else None
    @staticmethod
    def _round(value): return round(value, 6)
    @staticmethod
    def _midpoint(zone):
        try: return (int(str(zone).split("-")[0]) + 5) / 100
        except (TypeError, ValueError): return 0.0
    @staticmethod
    def _digest(value): return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    @staticmethod
    def _iso(value): return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
