"""V28 executor compatibility and immutable Decision Intelligence contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from .runtime_context import RuntimeContext

SCHEMA_VERSION = "2.0"
DECISION_SCHEMA_VERSION = "V28.DECISION_CONTEXT.1.0"
DECISION_POLICY_ID = "V28_DECISION_INTELLIGENCE_POLICY"
DECISION_POLICY_VERSION = "1.0.0"
FIELDS = frozenset({"schema_version", "brain_version", "runtime_version", "sequence_id", "heartbeat_unix",
"published_at", "decision", "direction", "entry_permission", "entry_state", "construction_action", "confidence",
"probability", "expected_value", "location_score", "position_budget_total", "position_budget_used",
"position_budget_remaining", "decision_reasons", "decision_trace", "fail_safe", "executable", "symbol", "volume",
"entry_price", "stop_loss", "take_profit"})


def _plain(value: Any) -> Any:
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


def replay_identity(payload: Mapping[str, Any]) -> str:
    """Return the policy-domain-separated canonical replay identity."""
    canonical = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(("V28_DECISION_REPLAY|" + canonical).encode()).hexdigest()


@dataclass(frozen=True)
class ExpectancyContext:
    status: str
    expected_quality: float
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    explanation: str
    evidence_reference: str
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"POSITIVE_EXPECTANCY", "EXPECTANCY_NOT_ESTABLISHED"}:
            raise ValueError("EXPECTANCY_STATUS_INVALID")
        if not isfinite(self.expected_quality) or not 0.0 <= self.expected_quality <= 1.0 or not self.explanation:
            raise ValueError("EXPECTANCY_CONTRACT_INVALID")
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence))
        object.__setattr__(self, "conflicting_evidence", tuple(self.conflicting_evidence))


@dataclass(frozen=True)
class RiskEligibility:
    status: str
    reasons: tuple[str, ...]
    explanation: str
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if (self.status not in {"RISK_ELIGIBLE", "RISK_REJECTED", "RISK_DEFERRED"}
                or not self.reasons or not self.explanation):
            raise ValueError("RISK_ELIGIBILITY_INVALID")
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True)
class Confidence:
    value: float
    band: str
    factors: Mapping[str, float]
    explanation: str
    sufficient: bool
    policy_version: str = DECISION_POLICY_VERSION

    def __post_init__(self) -> None:
        if (not isfinite(self.value) or not 0.0 <= self.value <= 1.0
                or self.band not in {"INSUFFICIENT", "SUFFICIENT", "HIGH"}):
            raise ValueError("CONFIDENCE_INVALID")
        if self.sufficient != (self.value >= 0.75) or not self.explanation:
            raise ValueError("CONFIDENCE_INCONSISTENT")
        object.__setattr__(self, "factors", _freeze(self.factors))


@dataclass(frozen=True)
class DecisionContext:
    decision: str
    direction: str
    expectancy: ExpectancyContext
    confidence: Confidence
    risk_eligibility: RiskEligibility
    decision_reason: str
    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]
    decision_lineage: Mapping[str, str]
    policy_references: tuple[str, ...]
    replay_identity: str
    policy_version: str = DECISION_POLICY_VERSION
    schema_version: str = DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.decision not in {"BUY", "SELL", "HOLD"}:
            raise ValueError("DECISION_INVALID")
        expected_direction = self.decision if self.decision != "HOLD" else "NONE"
        if self.direction != expected_direction or not self.decision_reason:
            raise ValueError("DECISION_DIRECTION_INVALID")
        if self.policy_version != DECISION_POLICY_VERSION or self.schema_version != DECISION_SCHEMA_VERSION:
            raise ValueError("DECISION_VERSION_INVALID")
        if len(self.replay_identity) != 64 or any(c not in "0123456789abcdef" for c in self.replay_identity):
            raise ValueError("DECISION_REPLAY_IDENTITY_INVALID")
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence))
        object.__setattr__(self, "conflicting_evidence", tuple(self.conflicting_evidence))
        object.__setattr__(self, "policy_references", tuple(self.policy_references))
        object.__setattr__(self, "decision_lineage", _freeze(self.decision_lineage))


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
