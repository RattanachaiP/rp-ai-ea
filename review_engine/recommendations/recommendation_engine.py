"""Pure deterministic construction of advisory recommendations from Insight documents only."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Mapping


class PriorityEngine:
    """Maps deterministic severity signals to the supported advisory priority levels."""
    LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATION")
    def calculate(self, category: str, metrics: Mapping[str, object]) -> str:
        drift = abs(float(metrics.get("calibration_drift") or 0))
        coverage = int(metrics.get("evidence_coverage") or 0)
        if drift >= .30: return "CRITICAL"
        if drift >= .15 or coverage < 3: return "HIGH"
        if category in {"ENTRY_QUALITY", "REVERSAL_SETUP", "SESSION_PERFORMANCE"}: return "MEDIUM"
        if category == "EVIDENCE_COVERAGE": return "LOW"
        return "INFORMATION"


class EvidenceChainBuilder:
    """Derives full lineage solely from lineage already embedded in an Insight."""
    def build(self, insight: Mapping[str, object]) -> dict[str, list[str]]:
        lineage = insight.get("lineage", {})
        if not isinstance(lineage, Mapping): raise ValueError("LINEAGE_MISSING")
        knowledge = sorted({str(value) for value in lineage.get("knowledge_ids", []) if str(value)})
        rows = lineage.get("evidence", [])
        if not isinstance(rows, list): raise ValueError("LINEAGE_EVIDENCE_INVALID")
        evidence, snapshots = set(), set()
        for row in rows:
            if not isinstance(row, Mapping): raise ValueError("LINEAGE_EVIDENCE_INVALID")
            evidence_id, snapshot_id = str(row.get("evidence_id", "")), str(row.get("snapshot_id", ""))
            if not evidence_id or not snapshot_id: raise ValueError("LINEAGE_INCOMPLETE")
            evidence.add(evidence_id); snapshots.add(snapshot_id)
        if not knowledge or not evidence or not snapshots: raise ValueError("LINEAGE_INCOMPLETE")
        return {"insight_ids": [str(insight.get("insight_version", ""))], "knowledge_ids": knowledge,
                "evidence_ids": sorted(evidence), "snapshot_ids": sorted(snapshots)}


class ImpactEstimator:
    """Historical-only estimates; no forecast or runtime authority is produced."""
    def estimate(self, insight: Mapping[str, object]) -> dict[str, object]:
        metrics = insight.get("metrics", {}) if isinstance(insight.get("metrics"), Mapping) else {}
        confidence = metrics.get("confidence_intelligence", {}) if isinstance(metrics.get("confidence_intelligence"), Mapping) else {}
        rankings = metrics.get("pattern_ranking", {}) if isinstance(metrics.get("pattern_ranking"), Mapping) else {}
        rows = rankings.get("by_average_rr", []) if isinstance(rankings.get("by_average_rr"), list) else []
        observed_rr = [float(row["average_rr"]) for row in rows if isinstance(row, Mapping) and isinstance(row.get("average_rr"), (int, float))]
        return {"scope": "HISTORICAL_ANALYTICAL_ESTIMATE_ONLY", "not_guaranteed_future_performance": True,
                "expected_win_rate_change": round(-abs(float(confidence.get("calibration_drift") or 0)), 6),
                "expected_profit_factor_change": None,
                "expected_rr_change": round(max(observed_rr) - min(observed_rr), 6) if len(observed_rr) > 1 else None,
                "expected_drawdown_change": None, "expected_trade_frequency_change": 0.0}


class RecommendationEngine:
    SCHEMA_VERSION = "5.0.0"; PRODUCER = "RAIP Recommendation Generator"; OWNER = "RAIP Recommendation Layer"
    def __init__(self, *, clock: Callable[[], datetime] | None = None, priority=None, chain=None, impact=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc)); self.priority = priority or PriorityEngine(); self.chain = chain or EvidenceChainBuilder(); self.impact = impact or ImpactEstimator()
    def generate(self, insights: Mapping[str, object] | list[Mapping[str, object]]) -> dict[str, object]:
        items = [insights] if isinstance(insights, Mapping) else sorted(insights, key=lambda row: str(row.get("insight_version", "")))
        if not items or any(str(item.get("schema_version")) != "4.0.0" or not str(item.get("insight_version", "")) for item in items): raise ValueError("INCOMPATIBLE_INSIGHT")
        chains = [self.chain.build(item) for item in items]
        chain = {key: sorted({value for item in chains for value in item[key]}) for key in ("insight_ids", "knowledge_ids", "evidence_ids", "snapshot_ids")}
        # Rules are evaluated per Insight, then de-duplicated by category. This preserves
        # all supporting lineage while making aggregation order-independent.
        rules = {}; metrics = {}
        for item in items:
            current = item.get("metrics", {}) if isinstance(item.get("metrics"), Mapping) else {}
            metrics = current
            for category, summary in self._rules(item, current): rules.setdefault(category, summary)
        source_version = items[0]["insight_version"] if len(items) == 1 else self._digest(chain["insight_ids"])
        recommendations = [self._recommendation(category, summary, metrics, chain, source_version) for category, summary in sorted(rules.items())]
        stable_records = [{key: value for key, value in record.items() if key != "created_at"} for record in recommendations]
        recommendation_version = self._digest({"insight_version": source_version, "recommendations": stable_records})
        return {"schema_version": self.SCHEMA_VERSION, "producer": self.PRODUCER, "owner": self.OWNER, "created_at": self._iso(self.clock()),
                "insight_version": source_version, "recommendation_version": recommendation_version,
                "lineage_hash": self._digest(chain), "recommendations": recommendations}
    def _rules(self, insight, metrics):
        summary = insight.get("summary", {}) if isinstance(insight.get("summary"), Mapping) else {}
        confidence = metrics.get("confidence_intelligence", {}) if isinstance(metrics.get("confidence_intelligence"), Mapping) else {}
        result = []
        if confidence.get("overconfident_regions"): result.append(("CONFIDENCE_BIAS", "Reduce Confidence Bias"))
        if summary.get("worst_performing_pattern") == "REVERSAL": result.append(("REVERSAL_SETUP", "Review Reversal Setup"))
        if summary.get("best_performing_pattern") == "TREND": result.append(("ENTRY_QUALITY", "Improve Trend Entry Quality"))
        if int(metrics.get("evidence_coverage") or 0) < 10: result.append(("EVIDENCE_COVERAGE", "Increase Evidence Coverage"))
        if summary.get("worst_session"): result.append(("SESSION_PERFORMANCE", "Review Session Performance"))
        return result or [("INFORMATION", "Review Available Intelligence")]
    def _recommendation(self, category, summary, metrics, chain, insight_version):
        identifier = self._digest({"insight": insight_version, "category": category, "lineage": chain})
        return {"recommendation_id": identifier, "created_at": self._iso(self.clock()), "schema_version": self.SCHEMA_VERSION,
                "priority": self.priority.calculate(category, metrics), "category": category, "summary": summary,
                "supporting_insights": chain["insight_ids"], "supporting_knowledge": chain["knowledge_ids"],
                "supporting_evidence": chain["evidence_ids"], "supporting_snapshots": chain["snapshot_ids"],
                "estimated_impact": self.impact.estimate({"metrics": metrics}), "validation_status": "PENDING", "producer": self.PRODUCER, "owner": self.OWNER}
    @staticmethod
    def _digest(value): return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    @staticmethod
    def _iso(value): return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
