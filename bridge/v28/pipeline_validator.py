"""Direct, read-only and fail-closed certification of every PR260--PR264 stage."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from .context_contracts import CONTEXT_TYPES, OpportunityContext
from .decision_contract import (DECISION_POLICY_ID, DECISION_POLICY_VERSION, DecisionContext,
                                decision_replay_identity)
from .execution_plan import ExecutionPlan, identity, parse_utc
from .execution_replay_validator import validate_execution_replay
from .executor_contract import ExecutorContract
from .market_snapshot import MarketSnapshot
from .publisher_contract import (BrokerSnapshot, PublishedExecutionPlan, RuntimeHealthSnapshot,
                                 canonical_json)
from .runtime_context import RuntimeContext

PR265_POLICY = "V28_END_TO_END_VALIDATION_POLICY@2.0.0"
RUNTIME_POLICY = "V28_RUNTIME_FOUNDATION_POLICY@1.0.0"
MARKET_POLICY = "V28_MARKET_INTELLIGENCE_POLICY@1.0.0"
RISK_POLICY = "V28_RISK_CONSTRUCTION_POLICY@1.1.0"
DECISION_POLICY = "V28_DECISION_INTELLIGENCE_POLICY@1.1.0"

def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"): return {k: _plain(getattr(value, k)) for k in value.__dataclass_fields__}
    if isinstance(value, Mapping): return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)): return sorted(_plain(v) for v in value)
    return value

def certification_identity(domain: str, payload: Any) -> str:
    raw = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256((domain + "|" + raw).encode()).hexdigest()

@dataclass(frozen=True)
class Campaign:
    campaign_identity: str; runtime_sequence_id: int; symbol: str; evaluation_time: str
    decision_replay_identity: str; plan_replay_identity: str; publication_replay_identity: str
    environment_identity: str; policy_reference: str = PR265_POLICY
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "campaign_identity"}
    def __post_init__(self):
        parse_utc(self.evaluation_time)
        if self.policy_reference != PR265_POLICY or type(self.runtime_sequence_id) is not int or not self.symbol: raise ValueError("CAMPAIGN_INVALID")
        if self.campaign_identity != certification_identity("V28_CERTIFICATION_CAMPAIGN", self.canonical_payload()): raise ValueError("CAMPAIGN_IDENTITY_INVALID")

def create_campaign(**values: Any) -> Campaign:
    values.setdefault("policy_reference", PR265_POLICY)
    return Campaign(**values, campaign_identity=certification_identity("V28_CERTIFICATION_CAMPAIGN", values))

@dataclass(frozen=True)
class MarketStateEvidence:
    sequence_id: int; symbol: str; heartbeat_unix: float; observed_at: str; source_authority: str
    policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        parse_utc(self.observed_at)
        if type(self.sequence_id) is not int or type(self.heartbeat_unix) not in (int, float) or not self.symbol or not self.source_authority: raise ValueError("MARKET_STATE_INVALID")
        if self.replay_identity != certification_identity("V28_MARKET_STATE_EVIDENCE", self.canonical_payload()): raise ValueError("MARKET_STATE_REPLAY_INVALID")

@dataclass(frozen=True)
class RuntimeFoundationEvidence:
    runtime_context: RuntimeContext; source_replay_identity: str; normalized: bool
    source_authority: str; boundary_healthy: bool; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if type(self.runtime_context) is not RuntimeContext or self.normalized is not True or self.boundary_healthy is not True: raise ValueError("RUNTIME_FOUNDATION_INVALID")
        if self.replay_identity != certification_identity("V28_RUNTIME_FOUNDATION_EVIDENCE", self.canonical_payload()): raise ValueError("RUNTIME_FOUNDATION_REPLAY_INVALID")

@dataclass(frozen=True)
class NormalizedMarketEvidence:
    snapshot: MarketSnapshot; market_state_replay_identity: str; evaluation_time: str
    source_authority: str; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        parse_utc(self.evaluation_time)
        if type(self.snapshot) is not MarketSnapshot or self.replay_identity != certification_identity("V28_NORMALIZED_MARKET_EVIDENCE", self.canonical_payload()): raise ValueError("NORMALIZED_MARKET_REPLAY_INVALID")

@dataclass(frozen=True)
class MarketIntelligenceEvidence:
    contexts: tuple[Any, ...]; normalized_market_replay_identity: str; sequence_id: int; symbol: str
    evaluation_time: str; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        parse_utc(self.evaluation_time)
        if len(self.contexts) != 7 or tuple(type(x) for x in self.contexts) != CONTEXT_TYPES: raise ValueError("MARKET_INTELLIGENCE_CONTEXTS_INVALID")
        if self.replay_identity != certification_identity("V28_MARKET_INTELLIGENCE_EVIDENCE", self.canonical_payload()): raise ValueError("MARKET_INTELLIGENCE_REPLAY_INVALID")

def bind_evidence(contract_type: type, domain: str, **values: Any):
    return contract_type(**values, replay_identity=certification_identity(domain, values))

@dataclass(frozen=True)
class BoundaryResult:
    boundary: str; status: str; checks: tuple[str, ...]; failures: tuple[str, ...]
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or (self.status == "FAIL") != bool(self.failures): raise ValueError("BOUNDARY_RESULT_INVALID")

@dataclass(frozen=True)
class PipelineValidationReport:
    status: str; campaign: Campaign; boundaries: tuple[BoundaryResult, ...]
    production_authorized: bool; policy_reference: str; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.production_authorized is not False or self.policy_reference != PR265_POLICY: raise ValueError("PIPELINE_REPORT_INVALID")
        if self.replay_identity != certification_identity("V28_PIPELINE_VALIDATION", self.canonical_payload()): raise ValueError("PIPELINE_REPORT_REPLAY_INVALID")

def report_identity_valid(report: Any, expected_type: type, domain: str) -> bool:
    return type(report) is expected_type and getattr(report, "replay_identity", None) == certification_identity(domain, report.canonical_payload())

def _boundary(name: str, checks: tuple[str, ...], failures: list[str]) -> BoundaryResult:
    return BoundaryResult(name, "FAIL" if failures else "PASS", checks, tuple(dict.fromkeys(failures)))

def _fresh(observed: datetime, now: datetime, maximum_age: float) -> bool:
    age = (now - observed).total_seconds(); return 0 <= age <= maximum_age

def validate_pipeline(*, campaign: Any, market_state: Any, runtime: Any, normalized_market: Any,
                      market_intelligence: Any, opportunity: Any, decision: Any, plan: Any,
                      contract: Any, health: Any, broker: Any, publication: Any) -> PipelineValidationReport:
    """Never raises for evidence errors: malformed stages become deterministic FAIL results."""
    valid_campaign = type(campaign) is Campaign and campaign.campaign_identity == certification_identity("V28_CERTIFICATION_CAMPAIGN", campaign.canonical_payload())
    if not valid_campaign:
        # A deterministic sentinel lets even a malformed campaign be reported.
        campaign = create_campaign(runtime_sequence_id=-1, symbol="INVALID", evaluation_time="1970-01-01T00:00:00Z",
            decision_replay_identity="INVALID", plan_replay_identity="INVALID", publication_replay_identity="INVALID", environment_identity="INVALID")
    now = parse_utc(campaign.evaluation_time)
    boundaries = []
    f = []
    if not valid_campaign: f.append("CAMPAIGN_INVALID")
    ms_valid = type(market_state) is MarketStateEvidence and market_state.replay_identity == certification_identity("V28_MARKET_STATE_EVIDENCE", market_state.canonical_payload())
    if not ms_valid: f.append("MARKET_STATE_INVALID")
    else:
        if market_state.sequence_id != campaign.runtime_sequence_id: f.append("MARKET_SEQUENCE_MISMATCH")
        if market_state.symbol != campaign.symbol: f.append("MARKET_SYMBOL_MISMATCH")
        if market_state.policy_reference != RUNTIME_POLICY: f.append("MARKET_POLICY_MISMATCH")
        if not _fresh(datetime.fromtimestamp(market_state.heartbeat_unix, timezone.utc), now, 5): f.append("MARKET_STATE_STALE_OR_FUTURE")
    boundaries.append(_boundary("RUNTIME_FOUNDATION", ("MARKET_REPLAY","SOURCE_SEQUENCE","HEARTBEAT","FRESHNESS","NORMALIZATION","SYMBOL","SOURCE_AUTHORITY","BOUNDARY_HEALTH","POLICY_REFERENCE"), f))
    f=[]
    rt_valid=type(runtime) is RuntimeFoundationEvidence and runtime.replay_identity==certification_identity("V28_RUNTIME_FOUNDATION_EVIDENCE",runtime.canonical_payload())
    nm_valid=type(normalized_market) is NormalizedMarketEvidence and normalized_market.replay_identity==certification_identity("V28_NORMALIZED_MARKET_EVIDENCE",normalized_market.canonical_payload())
    if not rt_valid: f.append("RUNTIME_EVIDENCE_INVALID")
    if not nm_valid: f.append("NORMALIZED_MARKET_INVALID")
    if rt_valid and ms_valid:
        ctx=runtime.runtime_context
        if runtime.source_replay_identity!=market_state.replay_identity: f.append("RUNTIME_SOURCE_LINEAGE_MISMATCH")
        if ctx.market.get("sequence_id")!=market_state.sequence_id or ctx.market.get("symbol")!=market_state.symbol: f.append("RUNTIME_MARKET_FIELDS_MISMATCH")
        if runtime.policy_reference!=RUNTIME_POLICY or not runtime.source_authority: f.append("RUNTIME_POLICY_OR_AUTHORITY_INVALID")
    if nm_valid and ms_valid:
        if normalized_market.market_state_replay_identity!=market_state.replay_identity: f.append("NORMALIZED_SOURCE_LINEAGE_MISMATCH")
        if normalized_market.snapshot.sequence_id!=market_state.sequence_id or normalized_market.snapshot.symbol!=market_state.symbol: f.append("NORMALIZED_MARKET_FIELDS_MISMATCH")
        if normalized_market.policy_reference!=MARKET_POLICY or normalized_market.snapshot.policy_version!="1.0.0": f.append("MARKET_POLICY_MISMATCH")
        if parse_utc(normalized_market.evaluation_time)!=now: f.append("NORMALIZED_EVALUATION_MISMATCH")
    boundaries.append(_boundary("MARKET_INTELLIGENCE", ("RUNTIME_CONTEXT_REPLAY","NORMALIZED_SNAPSHOT_REPLAY","SOURCE_LINEAGE","FIELD_CONSISTENCY","POLICY_LINEAGE"),f))
    f=[]
    mi_valid=type(market_intelligence) is MarketIntelligenceEvidence and market_intelligence.replay_identity==certification_identity("V28_MARKET_INTELLIGENCE_EVIDENCE",market_intelligence.canonical_payload())
    if not mi_valid: f.append("MARKET_INTELLIGENCE_INVALID")
    if type(opportunity) is not OpportunityContext: f.append("OPPORTUNITY_CONTEXT_INVALID")
    dec_valid=type(decision) is DecisionContext and decision.replay_identity==decision_replay_identity(decision.canonical_payload())
    if not dec_valid: f.append("DECISION_CONTEXT_INVALID")
    if mi_valid and nm_valid:
        if market_intelligence.normalized_market_replay_identity!=normalized_market.replay_identity: f.append("INTELLIGENCE_SOURCE_LINEAGE_MISMATCH")
        if (market_intelligence.sequence_id,market_intelligence.symbol)!=(campaign.runtime_sequence_id,campaign.symbol): f.append("MARKET_DECISION_FIELDS_MISMATCH")
        if market_intelligence.evaluation_time!=campaign.evaluation_time: f.append("INTELLIGENCE_EVALUATION_MISMATCH")
        if market_intelligence.policy_reference!=MARKET_POLICY: f.append("INTELLIGENCE_POLICY_MISMATCH")
        if type(opportunity) is OpportunityContext and market_intelligence.contexts[-1] != opportunity: f.append("OPPORTUNITY_LINEAGE_MISMATCH")
    if dec_valid:
        if decision.replay_identity!=campaign.decision_replay_identity: f.append("DECISION_CAMPAIGN_MISMATCH")
        if decision.candidate.symbol!=campaign.symbol: f.append("MARKET_DECISION_SYMBOL_MISMATCH")
        if decision.policy_version!=DECISION_POLICY_VERSION or f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}" not in decision.policy_references: f.append("DECISION_POLICY_MISMATCH")
        if type(opportunity) is OpportunityContext and decision.candidate.opportunity_evidence_id!=opportunity.evidence["evidence_id"]: f.append("OPPORTUNITY_DECISION_LINEAGE_MISMATCH")
    boundaries.append(_boundary("DECISION_INTELLIGENCE",("MARKET_INTELLIGENCE_REPLAY","OPPORTUNITY_REPLAY","DECISION_REPLAY","SEQUENCE_SYMBOL_TIME","POLICY_LINEAGE","SOURCE_LINEAGE"),f))
    f=[]
    plan_valid=type(plan) is ExecutionPlan and plan.replay_identity==identity("V28_EXECUTION_PLAN_REPLAY",plan.canonical_payload())
    if not plan_valid: f.append("EXECUTION_PLAN_INVALID")
    elif dec_valid:
        if plan.decision_replay_identity!=decision.replay_identity or plan.replay_identity!=campaign.plan_replay_identity: f.append("RISK_LINEAGE_MISMATCH")
        if plan.runtime_sequence_id!=campaign.runtime_sequence_id or plan.symbol!=campaign.symbol: f.append("RISK_FIELDS_MISMATCH")
        if parse_utc(plan.evaluation_time)>now: f.append("RISK_EVALUATION_FUTURE")
        if plan.policy_references!=(RISK_POLICY,DECISION_POLICY): f.append("RISK_POLICY_INVALID")
    boundaries.append(_boundary("RISK_CONSTRUCTION",("PLAN_REPLAY","DECISION_LINEAGE","SEQUENCE_SYMBOL_TIME","POLICY_LINEAGE"),f))
    f=[]
    required=(type(contract) is ExecutorContract,type(health) is RuntimeHealthSnapshot,type(broker) is BrokerSnapshot,type(publication) is PublishedExecutionPlan)
    if not all(required): f.append("EXECUTION_ARTIFACT_MISSING_OR_INVALID")
    elif plan_valid:
        replay=validate_execution_replay(plan,contract,health,broker,publication,evaluation_time=campaign.evaluation_time)
        if not replay.valid: f.extend(replay.reasons)
        if contract.policy_reference!=RISK_POLICY: f.append("EXECUTOR_CONTRACT_POLICY_MISMATCH")
        if health.policy_reference!=broker.policy_reference or publication.policy_reference!=health.policy_reference: f.append("EXECUTION_POLICY_LINEAGE_MISMATCH")
        if publication.publication_replay_identity!=campaign.publication_replay_identity: f.append("PUBLICATION_CAMPAIGN_MISMATCH")
        if not all((publication.publisher_authority,publication.publisher_instance_identity,publication.destination_identity)) or publication.generation<1: f.append("PUBLICATION_AUTHORITY_INVALID")
        if publication.canonical_plan_json!=canonical_json(plan.canonical_payload()): f.append("PUBLICATION_CANONICAL_JSON_MISMATCH")
        if parse_utc(publication.publication_timestamp)<parse_utc(plan.evaluation_time): f.append("PUBLICATION_BEFORE_PLAN")
    boundaries.append(_boundary("EXECUTION_INTEGRATION",("CONTRACT_REPLAY","HEALTH_FRESHNESS","BROKER_FRESHNESS","POLICY_LINEAGE","PUBLICATION_REPLAY","CANONICAL_JSON","PAYLOAD_HASH","PUBLISHER_AUTHORITY","DESTINATION_GENERATION","PUBLICATION_CHRONOLOGY"),f))
    values=dict(status="PASS" if all(x.status=="PASS" for x in boundaries) else "FAIL",campaign=campaign,boundaries=tuple(boundaries),production_authorized=False,policy_reference=PR265_POLICY)
    return PipelineValidationReport(**values,replay_identity=certification_identity("V28_PIPELINE_VALIDATION",values))
