"""V28 executor compatibility and immutable Decision Intelligence contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping
from .runtime_context import RuntimeContext

SCHEMA_VERSION = "2.0"
DECISION_SCHEMA_VERSION = "V28.DECISION_CONTEXT.1.1"
EVIDENCE_SCHEMA_VERSION = "V28.EXPECTANCY_EVIDENCE.1.0"
CANDIDATE_SCHEMA_VERSION = "V28.DECISION_CANDIDATE.1.0"
DECISION_POLICY_ID = "V28_DECISION_INTELLIGENCE_POLICY"
DECISION_POLICY_VERSION = "1.1.0"
FIELDS = frozenset({"schema_version", "brain_version", "runtime_version", "sequence_id", "heartbeat_unix",
"published_at", "decision", "direction", "entry_permission", "entry_state", "construction_action", "confidence",
"probability", "expected_value", "location_score", "position_budget_total", "position_budget_used",
"position_budget_remaining", "decision_reasons", "decision_trace", "fail_safe", "executable", "symbol", "volume",
"entry_price", "stop_loss", "take_profit"})


def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {field: _plain(getattr(value, field)) for field in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


def _digest(domain: str, payload: Any) -> str:
    canonical = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256((domain + "|" + canonical).encode()).hexdigest()


@dataclass(frozen=True)
class ExpectancyEvidenceRecord:
    evidence_id: str
    replay_identity: str
    source_authority: str
    symbol: str
    timeframe: str
    opportunity_archetype: str
    market_side_context: str
    authorized_direction: str
    regime_scope: str
    market_policy_version: str
    execution_model_id: str
    cost_model_id: str
    sample_size: int
    sample_period_start: str
    sample_period_end: str
    win_probability: float
    average_win_r: float
    average_loss_r: float
    expected_cost_r: float
    net_expectancy_r: float
    statistical_method: str
    confidence_measure: float
    lower_confidence_bound_r: float
    return_variance: float
    maximum_drawdown_r: float
    evidence_quality: str
    recency_status: str
    expires_on: str
    costs_included: bool
    slippage_included: bool
    duplicates_excluded: bool
    out_of_sample: bool
    sample_scope_consistent: bool
    policy_version: str = DECISION_POLICY_VERSION
    schema_version: str = EVIDENCE_SCHEMA_VERSION

    def identity_payload(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name not in {"evidence_id", "replay_identity"}}

    def identity_valid(self) -> bool:
        return (self.evidence_id == _digest("V28_EXPECTANCY_EVIDENCE_ID", self.identity_payload())
                and self.replay_identity == _digest("V28_EXPECTANCY_EVIDENCE_REPLAY", self.identity_payload()))

    def __post_init__(self) -> None:
        if self.schema_version != EVIDENCE_SCHEMA_VERSION or self.policy_version != DECISION_POLICY_VERSION:
            raise ValueError("EXPECTANCY_EVIDENCE_VERSION_INVALID")
        if not all((self.source_authority, self.symbol, self.timeframe, self.opportunity_archetype,
                    self.execution_model_id, self.cost_model_id, self.statistical_method)):
            raise ValueError("EXPECTANCY_EVIDENCE_SCOPE_INVALID")
        if self.market_side_context not in {"UPWARD", "DOWNWARD"} or self.authorized_direction not in {"BUY", "SELL"}:
            raise ValueError("EXPECTANCY_EVIDENCE_DIRECTION_INVALID")
        numeric = (self.win_probability, self.average_win_r, self.average_loss_r, self.expected_cost_r,
                   self.net_expectancy_r, self.confidence_measure, self.lower_confidence_bound_r,
                   self.return_variance, self.maximum_drawdown_r)
        if any(type(x) not in (int, float) or not isfinite(x) for x in numeric) or type(self.sample_size) is not int:
            raise ValueError("EXPECTANCY_EVIDENCE_NUMERIC_INVALID")
        start, end, expiry = map(date.fromisoformat, (self.sample_period_start, self.sample_period_end, self.expires_on))
        if start > end or expiry < end:
            raise ValueError("EXPECTANCY_EVIDENCE_DATES_INVALID")
        if not self.identity_valid():
            raise ValueError("EXPECTANCY_EVIDENCE_IDENTITY_INVALID")


def create_expectancy_evidence(**values: Any) -> ExpectancyEvidenceRecord:
    """Owner construction path: calculate both identities from complete canonical content."""
    payload = dict(values)
    payload.setdefault("policy_version", DECISION_POLICY_VERSION)
    payload.setdefault("schema_version", EVIDENCE_SCHEMA_VERSION)
    evidence_id = _digest("V28_EXPECTANCY_EVIDENCE_ID", payload)
    replay = _digest("V28_EXPECTANCY_EVIDENCE_REPLAY", payload)
    return ExpectancyEvidenceRecord(evidence_id=evidence_id, replay_identity=replay, **payload)


@dataclass(frozen=True)
class DecisionCandidate:
    symbol: str
    timeframe: str
    opportunity_evidence_id: str
    opportunity_archetype: str
    market_side_context: str
    regime: str
    market_policy_version: str
    execution_model_id: str
    cost_model_id: str
    direction: str
    evidence_replay_identity: str
    authorized: bool
    authorization_reasons: tuple[str, ...]
    schema_version: str = CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CANDIDATE_SCHEMA_VERSION or self.direction not in {"BUY", "SELL", "NONE"}:
            raise ValueError("DECISION_CANDIDATE_INVALID")
        if self.authorized and (self.direction == "NONE" or not self.evidence_replay_identity):
            raise ValueError("DECISION_CANDIDATE_AUTHORITY_INVALID")
        if self.authorized and self.authorization_reasons != ("ALL_SCOPE_BINDINGS_VERIFIED",):
            raise ValueError("DECISION_CANDIDATE_BINDING_INVALID")
        object.__setattr__(self, "authorization_reasons", tuple(self.authorization_reasons))


@dataclass(frozen=True)
class ExpectancyContext:
    status: str
    evidence_quality: str
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    explanation: str
    evidence_replay_identity: str
    lower_confidence_bound_r: float | None
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"POSITIVE_EXPECTANCY", "EXPECTANCY_NOT_ESTABLISHED"}:
            raise ValueError("EXPECTANCY_CONTEXT_INVALID")
        if self.evidence_quality not in {"VALID", "DEGRADED", "INSUFFICIENT", "FAIL_CLOSED"}:
            raise ValueError("EXPECTANCY_QUALITY_INVALID")
        if not self.explanation or not self.evidence_replay_identity:
            raise ValueError("EXPECTANCY_LINEAGE_INVALID")
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence))
        object.__setattr__(self, "conflicting_evidence", tuple(self.conflicting_evidence))


@dataclass(frozen=True)
class DecisionRiskPrecheck:
    status: str
    reasons: tuple[str, ...]
    explanation: str
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"RISK_REVIEW_READY", "DECISION_RISK_PRECHECK_REJECTED", "DECISION_RISK_PRECHECK_DEFERRED"}:
            raise ValueError("RISK_PRECHECK_INVALID")
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not self.reasons or not self.explanation:
            raise ValueError("RISK_PRECHECK_EXPLANATION_INVALID")


@dataclass(frozen=True)
class Confidence:
    assessment: str
    confidence_measure: float | None
    basis: tuple[str, ...]
    explanation: str
    sufficient: bool
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.assessment not in {"GOVERNED_EVIDENCE_SUFFICIENT", "GOVERNED_EVIDENCE_INSUFFICIENT"}:
            raise ValueError("CONFIDENCE_INVALID")
        if self.sufficient != (self.assessment == "GOVERNED_EVIDENCE_SUFFICIENT"):
            raise ValueError("CONFIDENCE_INCONSISTENT")
        if self.confidence_measure is not None and (not isfinite(self.confidence_measure)
                                                    or not 0 <= self.confidence_measure <= 1):
            raise ValueError("CONFIDENCE_MEASURE_INVALID")
        if not self.basis or not self.explanation:
            raise ValueError("CONFIDENCE_EXPLANATION_INVALID")
        object.__setattr__(self, "basis", tuple(self.basis))


@dataclass(frozen=True)
class DecisionContext:
    decision: str
    direction: str
    expectancy: ExpectancyContext
    confidence: Confidence
    risk_precheck: DecisionRiskPrecheck
    candidate: DecisionCandidate
    decision_reason: str
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    decision_lineage: Mapping[str, str]
    policy_references: tuple[str, ...]
    replay_identity: str
    policy_version: str = DECISION_POLICY_VERSION
    schema_version: str = DECISION_SCHEMA_VERSION

    def canonical_payload(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "replay_identity"}

    def __post_init__(self) -> None:
        if self.decision not in {"BUY", "SELL", "HOLD"} or self.direction != (self.decision if self.decision != "HOLD" else "NONE"):
            raise ValueError("DECISION_DIRECTION_INVALID")
        if self.policy_version != DECISION_POLICY_VERSION or self.schema_version != DECISION_SCHEMA_VERSION:
            raise ValueError("DECISION_VERSION_INVALID")
        complete_lineage = (self.decision_lineage.get("opportunity_evidence_id") == self.candidate.opportunity_evidence_id
            and self.decision_lineage.get("expectancy_evidence_replay_identity") == self.expectancy.evidence_replay_identity
            == self.candidate.evidence_replay_identity
            and self.decision_lineage.get("market_policy") == self.candidate.market_policy_version
            and self.decision_lineage.get("decision_policy") == f"{DECISION_POLICY_ID}@{DECISION_POLICY_VERSION}")
        if self.decision in {"BUY", "SELL"} and not (self.expectancy.status == "POSITIVE_EXPECTANCY"
                and self.risk_precheck.status == "RISK_REVIEW_READY" and self.confidence.sufficient
                and self.candidate.authorized and self.candidate.direction == self.direction and complete_lineage):
            raise ValueError("DECISION_AUTHORITY_INVARIANT")
        if self.replay_identity != _digest("V28_DECISION_REPLAY", self.canonical_payload()):
            raise ValueError("DECISION_REPLAY_IDENTITY_INVALID")
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence))
        object.__setattr__(self, "conflicting_evidence", tuple(self.conflicting_evidence))
        object.__setattr__(self, "policy_references", tuple(self.policy_references))
        object.__setattr__(self, "decision_lineage", _freeze(self.decision_lineage))


def decision_replay_identity(payload: Mapping[str, Any]) -> str:
    return _digest("V28_DECISION_REPLAY", payload)
def build_decision(context: RuntimeContext, *, now: float) -> dict[str, Any]:
    """Build the sole PR-A outcome; there is deliberately no action input."""
    decision = {
        "schema_version": SCHEMA_VERSION, "brain_version": "V28.PR-A", "runtime_version": context.runtime_version,
        "sequence_id": int(context.market["sequence_id"]),
        # Executor compatibility: heartbeat remains the source Writer heartbeat; published_at is decision time.
        "heartbeat_unix": context.source_heartbeat_unix,
        "published_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision": "HOLD", "direction": "NONE", "entry_permission": False, "entry_state": "HOLD",
        "construction_action": "NO_ACTION", "confidence": 0.0, "probability": 0.0, "expected_value": 0.0,
        "location_score": 0.0, "position_budget_total": 0.0, "position_budget_used": 0.0,
        "position_budget_remaining": 0.0, "decision_reasons": ["V28_PR_A_FOUNDATION_HOLD"],
        "decision_trace": ["MARKET_VALID", "HEARTBEAT_VALID", "FRESHNESS_VALID", "NORMALIZED"],
        # Existing Executor semantics reserve fail_safe=true for its WAIT/FAIL_SAFE envelope. This governed HOLD
        # is non-executable but schema-valid, so false avoids violating the unchanged Executor contract.
        "fail_safe": False, "executable": False, "symbol": str(context.market["symbol"]), "volume": 0.0,
        "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0,
    }
    validate_pr_a_decision(decision)
    return decision


def validate_pr_a_decision(value: object) -> None:
    """Deterministic complete validator used at construction and publication."""
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("DECISION_SCHEMA_FIELDS")
    consts = {"schema_version": "2.0", "brain_version": "V28.PR-A", "runtime_version": "V28.PR-A",
              "decision": "HOLD", "direction": "NONE", "entry_permission": False, "entry_state": "HOLD",
              "construction_action": "NO_ACTION", "fail_safe": False, "executable": False, "volume": 0.0,
              "entry_price": 0.0, "stop_loss": 0.0, "take_profit": 0.0, "confidence": 0.0,
              "probability": 0.0, "expected_value": 0.0, "location_score": 0.0,
              "position_budget_total": 0.0, "position_budget_used": 0.0, "position_budget_remaining": 0.0}
    if any(value[key] != expected or type(value[key]) is not type(expected) for key, expected in consts.items()):
        raise ValueError("DECISION_SCHEMA_CONST")
    if type(value["sequence_id"]) is not int or value["sequence_id"] < 0:
        raise ValueError("DECISION_SCHEMA_SEQUENCE")
    numeric = ("heartbeat_unix", "confidence", "probability", "expected_value", "location_score",
               "position_budget_total", "position_budget_used", "position_budget_remaining")
    if any(type(value[key]) not in (int, float) or not isfinite(value[key]) for key in numeric):
        raise ValueError("DECISION_SCHEMA_NUMBER")
    if value["heartbeat_unix"] <= 0 or type(value["symbol"]) is not str or not value["symbol"]:
        raise ValueError("DECISION_SCHEMA_VALUE")
    if not isinstance(value["published_at"], str) or not value["published_at"].endswith("Z"):
        raise ValueError("DECISION_SCHEMA_TIMESTAMP")
    try:
        parsed_timestamp = datetime.fromisoformat(value["published_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("DECISION_SCHEMA_TIMESTAMP") from error
    if parsed_timestamp.tzinfo is None:
        raise ValueError("DECISION_SCHEMA_TIMESTAMP")
    for key in ("decision_reasons", "decision_trace"):
        if type(value[key]) is not list or not all(type(item) is str for item in value[key]):
            raise ValueError("DECISION_SCHEMA_ARRAY")
