"""Read-only deterministic evaluator for applicable gateway knowledge."""
from __future__ import annotations
from dataclasses import dataclass
from .models import ApplicableKnowledge, ApplicabilityReport, GatewayKnowledge, GatewaySnapshot, RuntimeContext

class ApplicabilityEvaluationError(ValueError): pass
@dataclass(frozen=True)
class ApplicabilityConfig:
    schema_version: str = "1.0"; configuration_version: str = "1.0"
    known_sessions: tuple[str, ...] = ("ASIA", "LONDON", "NEW_YORK")
    known_regimes: tuple[str, ...] = ("RANGE", "TREND", "TRANSITION")

class KnowledgeApplicabilityEngine:
    """Consumes only DTOs; never reads a registry, storage, or decision system."""
    def __init__(self, config: ApplicabilityConfig = ApplicabilityConfig(), report_repository=None):
        self.config, self._reports, self._last = config, report_repository, None
    def evaluate(self, snapshot: GatewaySnapshot, context: RuntimeContext) -> ApplicabilityReport:
        self._validate(snapshot, context)
        seen=set(); accepted=[]; rejected=[]
        for record in sorted(snapshot.records, key=lambda x: (x.semantic_identity, x.knowledge_uuid)):
            if record.knowledge_uuid in seen: raise ApplicabilityEvaluationError("DUPLICATE_CANDIDATE")
            seen.add(record.knowledge_uuid); codes=self._match(record, context)
            if any(code.endswith("MISMATCH") or code.startswith("UNSUPPORTED") or code == "FEATURE_MISMATCH" for code in codes):
                rejected.append((record.knowledge_uuid, tuple(codes))); continue
            factors=tuple(code for code in codes if code in {"SYMBOL_MATCH", "SESSION_MATCH", "TIMEFRAME_MATCH", "REGIME_MATCH", "EXECUTION_PROFILE_MATCH", "RUNTIME_VERSION_MATCH"})
            score=len(factors) / 6.0
            accepted.append(ApplicableKnowledge(record.knowledge_uuid, record.semantic_identity, score, record.priority, record.confidence, factors, tuple(codes), snapshot.snapshot_digest, record.registry_sequence))
        # one semantic identity can select exactly one candidate; highest priority then score/confidence and stable UUID.
        winners={}
        for item in accepted:
            old=winners.get(item.semantic_identity)
            if old is None or (-item.priority, -item.applicability_score, -item.confidence, item.knowledge_uuid) < (-old.priority, -old.applicability_score, -old.confidence, old.knowledge_uuid): winners[item.semantic_identity]=item
        for item in accepted:
            winner = winners[item.semantic_identity]
            if item != winner:
                rejected.append((item.knowledge_uuid, item.reason_codes + ("CONFLICT_SUPERSEDED",)))
        selected=tuple(sorted(winners.values(), key=lambda x: (-x.priority, -x.applicability_score, -x.confidence, x.semantic_identity, x.knowledge_uuid)))
        confidence=sum(x.confidence * x.applicability_score for x in selected) / len(selected) if selected else 0.0
        report=ApplicabilityReport(snapshot.snapshot_digest, context, selected, tuple(sorted(rejected)), confidence)
        self._last=report
        if self._reports is not None: self._reports.append(report)
        return report
    def resolve(self, snapshot, context): return self.evaluate(snapshot, context).applicable
    def lookup(self, knowledge_uuid): return next((x for x in self._last.applicable if x.knowledge_uuid == knowledge_uuid), None) if self._last else None
    def list_applicable(self): return self._last.applicable if self._last else ()
    def report(self): return self._last
    def _validate(self, snapshot, context):
        if not isinstance(snapshot, GatewaySnapshot): raise ApplicabilityEvaluationError("MISSING_SNAPSHOT")
        if not isinstance(context, RuntimeContext): raise ApplicabilityEvaluationError("INVALID_RUNTIME_CONTEXT")
        if not snapshot.digest_valid(): raise ApplicabilityEvaluationError("DIGEST_MISMATCH")
        if snapshot.schema_version != self.config.schema_version: raise ApplicabilityEvaluationError("UNSUPPORTED_SCHEMA")
        if snapshot.configuration_version != self.config.configuration_version: raise ApplicabilityEvaluationError("UNSUPPORTED_CONFIGURATION")
        if context.session not in self.config.known_sessions: raise ApplicabilityEvaluationError("UNKNOWN_SESSION")
        if context.market_regime not in self.config.known_regimes: raise ApplicabilityEvaluationError("UNKNOWN_REGIME")
    def _match(self, r, c):
        pairs=(("SYMBOL", c.symbol, r.symbols),("SESSION",c.session,r.sessions),("TIMEFRAME",c.timeframe,r.timeframes),("REGIME",c.market_regime,r.market_regimes),("EXECUTION_PROFILE",c.execution_profile,r.execution_profiles))
        codes=[f"{name}_MATCH" if value in allowed else f"{name}_MISMATCH" for name,value,allowed in pairs]
        codes += ["SCHEMA_MATCH" if r.schema_version == self.config.schema_version else "UNSUPPORTED_SCHEMA", "CONFIGURATION_MATCH" if r.configuration_version == self.config.configuration_version else "UNSUPPORTED_CONFIGURATION", "RUNTIME_VERSION_MATCH" if c.runtime_version in r.supported_runtime_versions else "UNSUPPORTED_RUNTIME_VERSION", "FEATURE_MATCH" if set(r.required_features).issubset(c.feature_flags) else "FEATURE_MISMATCH"]
        return codes
