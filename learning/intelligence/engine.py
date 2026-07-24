"""PR163 offline-only evidence aggregation and advisory recommendation engine."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt
from typing import Iterable
from runtime.decision_knowledge_observation import DecisionKnowledgeObservationRecord
from runtime.decision_outcome_observation import DecisionOutcomeObservationRecord
from .models import *

class LearningIntelligenceError(ValueError): pass

def _verify_knowledge(record):
    # Reconstructing validates UUIDs, digests, contract version and canonical order.
    try:
        verified = DecisionKnowledgeObservationRecord(record.decision_uuid, record.decision_cycle_uuid, record.decision_digest,
            record.report_uuid, record.report_digest, record.snapshot_digest, record.knowledge_observation,
            record.observation_timestamp, record.observation_digest, record.observation_uuid, record.contract_version, record.observation_mode)
    except (TypeError, ValueError, AttributeError) as exc: raise LearningIntelligenceError("CORRUPTED_KNOWLEDGE_OBSERVATION") from exc
    if verified != record: raise LearningIntelligenceError("CORRUPTED_KNOWLEDGE_OBSERVATION")

def _verify_outcome(record):
    try:
        verified = DecisionOutcomeObservationRecord(**record.to_dict())
    except (TypeError, ValueError, AttributeError) as exc: raise LearningIntelligenceError("CORRUPTED_OUTCOME_OBSERVATION") from exc
    if verified != record: raise LearningIntelligenceError("CORRUPTED_OUTCOME_OBSERVATION")

def _session(timestamp: str) -> str:
    hour = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).hour
    return "ASIA" if hour < 7 else "LONDON" if hour < 13 else "NEW_YORK" if hour < 21 else "OFF_HOURS"

def _wilson(wins: int, total: int) -> tuple[float, float]:
    if not total: return (0.0, 0.0)
    z=1.959963984540054; p=wins/total; d=1+z*z/total; c=(p+z*z/(2*total))/d; m=z*sqrt((p*(1-p)+z*z/(4*total))/total)/d
    return (max(0.0,c-m), min(1.0,c+m))

def _pf(values):
    positive=sum(x for x in values if x>0); loss=-sum(x for x in values if x<0)
    return positive/loss if loss else None

def _context_stats(rows):
    values=[r.net_profit for r in rows]; n=len(rows); wins=sum(v>0 for v in values); pf=_pf(values)
    return {"usage_count": n, "win_rate": wins/n if n else 0.0, "net_profit": sum(values), "profit_factor": pf}

class LearningIntelligenceEngine:
    """Consumes immutable PR161/PR162 records only; it has no runtime dependencies."""
    def __init__(self, thresholds: LearningThresholds | None = None): self.thresholds=thresholds or LearningThresholds()
    def evaluate(self, knowledge_records: Iterable[DecisionKnowledgeObservationRecord], outcome_records: Iterable[DecisionOutcomeObservationRecord]):
        knowledge_records=tuple(knowledge_records); outcome_records=tuple(outcome_records)
        by_observation={}
        for record in knowledge_records:
            if not isinstance(record, DecisionKnowledgeObservationRecord): raise LearningIntelligenceError("UNSUPPORTED_KNOWLEDGE_CONTRACT")
            _verify_knowledge(record)
            if record.observation_uuid in by_observation: raise LearningIntelligenceError("DUPLICATE_KNOWLEDGE_OBSERVATION")
            by_observation[record.observation_uuid]=record
        outcomes=[]; seen=set()
        for record in outcome_records:
            if not isinstance(record, DecisionOutcomeObservationRecord): raise LearningIntelligenceError("UNSUPPORTED_OUTCOME_CONTRACT")
            _verify_outcome(record)
            if record.observation_uuid in seen: raise LearningIntelligenceError("DUPLICATE_OUTCOME_OBSERVATION")
            seen.add(record.observation_uuid)
            source=by_observation.get(record.decision_observation_uuid)
            if source is None or source.decision_uuid != record.decision_uuid: raise LearningIntelligenceError("INCONSISTENT_EVIDENCE")
            outcomes.append((record, source))
        grouped=defaultdict(list)
        for outcome, source in outcomes:
            for ref in source.knowledge_observation.resolved_knowledge:
                grouped[(ref.knowledge_uuid, ref.semantic_identity)].append(outcome)
        statistics=tuple(self._statistics(key, rows) for key, rows in sorted(grouped.items()))
        recommendations=tuple(self._recommend(stat) for stat in statistics)
        return statistics, recommendations
    @staticmethod
    def build_summary(trades, statistics, recommendations):
        return LearningSummary(trades=trades, knowledge_evaluated=len(statistics),
            promotion_candidates=sum(x.recommendation == "PROMOTE" for x in recommendations),
            review_required=sum(x.recommendation == "REVIEW" for x in recommendations),
            rejected=sum(x.recommendation == "REJECT" for x in recommendations),
            drift_detected=any(x.drift_detected for x in statistics))
    def daily_report(self, report_date, knowledge_records, outcome_records):
        try: datetime.strptime(report_date, "%Y-%m-%d")
        except (TypeError, ValueError) as exc: raise LearningIntelligenceError("INVALID_REPORT_DATE") from exc
        knowledge_records, outcome_records = tuple(knowledge_records), tuple(outcome_records)
        statistics, recommendations = self.evaluate(knowledge_records, outcome_records)
        return LearningDailyReport(report_date, self.build_summary(len(outcome_records), statistics, recommendations), statistics, recommendations)
    def weekly_report(self, week_start, knowledge_records, outcome_records):
        try: datetime.strptime(week_start, "%Y-%m-%d")
        except (TypeError, ValueError) as exc: raise LearningIntelligenceError("INVALID_WEEK_START") from exc
        knowledge_records, outcome_records = tuple(knowledge_records), tuple(outcome_records)
        statistics, recommendations = self.evaluate(knowledge_records, outcome_records)
        return LearningWeeklyReport(week_start, self.build_summary(len(outcome_records), statistics, recommendations), statistics, recommendations)
    def _statistics(self, key, rows):
        values=[r.net_profit for r in rows]; n=len(rows); wins=sum(x>0 for x in values); losses=sum(x<0 for x in values)
        running=peak=drawdown=0.0
        for v in values:
            running+=v; peak=max(peak,running); drawdown=max(drawdown,peak-running)
        contexts=defaultdict(lambda: defaultdict(list))
        for row in rows:
            contexts["symbol"][row.symbol].append(row); contexts["session"][_session(row.entry_time)].append(row)
            # PR161/162 do not carry these dimensions; use explicit UNKNOWN rather than infer runtime state.
            for dimension in ("timeframe", "market_regime", "volatility_class", "trend_state", "execution_profile"): contexts[dimension]["UNKNOWN"].append(row)
        context={d:{k:_context_stats(v) for k,v in sorted(vals.items())} for d,vals in sorted(contexts.items())}
        pf=_pf(values); rr=[r.maximum_favorable_excursion/r.maximum_adverse_excursion for r in rows if r.maximum_adverse_excursion>0]
        ci=_wilson(wins,n); confidence=ci[0]
        recent=rows[-self.thresholds.drift_recent_trades:]; earlier=rows[:-self.thresholds.drift_recent_trades]
        drift=bool(earlier and (_pf([x.net_profit for x in recent]) or 0) < (_pf([x.net_profit for x in earlier]) or 0)*self.thresholds.drift_profit_factor_drop)
        return LearningKnowledgeStatistics(key[0],key[1],n,wins,losses,wins/n if n else 0.0,losses/n if n else 0.0,sum(max(0,r.gross_profit) for r in rows),sum(values),pf or None,sum(values)/n if n else 0.0,sum(r.holding_time_seconds for r in rows)/n if n else 0.0,sum(r.maximum_favorable_excursion for r in rows)/n if n else 0.0,sum(r.maximum_adverse_excursion for r in rows)/n if n else 0.0,drawdown,sum(rr)/len(rr) if rr else None,ci,confidence,context,drift)
    def _recommend(self, stat):
        t=self.thresholds; sessions=len(stat.context["session"])
        minimum=stat.usage_count>=t.minimum_trades and stat.wins>=t.minimum_wins and sessions>=t.minimum_sessions and stat.confidence>=t.minimum_confidence
        if not minimum: kind="COLLECT_MORE_DATA"; reasons=("MINIMUM_SAMPLE_NOT_MET",)
        elif stat.drift_detected: kind="REVIEW"; reasons=("DRIFT_DETECTED",)
        elif (stat.profit_factor is None or stat.profit_factor >= t.promote_min_profit_factor) and stat.expectancy >= t.promote_min_expectancy: kind="PROMOTE"; reasons=("STATISTICAL_THRESHOLD_MET",)
        elif stat.profit_factor is not None and stat.profit_factor <= t.reject_max_profit_factor: kind="REJECT"; reasons=("UNDERPERFORMANCE",)
        else: kind="NO_ACTION"; reasons=("NO_ACTIONABLE_SIGNAL",)
        return LearningRecommendation(stat.knowledge_uuid,stat.semantic_identity,kind,stat.confidence,reasons)
