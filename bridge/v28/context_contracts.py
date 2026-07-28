"""Immutable, validated V28 market-language contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, ClassVar, Mapping

SCHEMA_VERSION = "V28.MARKET_CONTEXT.1.0"
QUALITY = frozenset({"VALID", "INSUFFICIENT", "DEGRADED", "FAIL_CLOSED"})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class ContextBase:
    state: str
    evidence: Mapping[str, Any]
    explanation: str
    data_quality: str
    policy_id: str
    policy_version: str
    schema_version: str = SCHEMA_VERSION
    ALLOWED: ClassVar[frozenset[str]] = frozenset()

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.state not in self.ALLOWED:
            raise ValueError(f"{type(self).__name__}_ONTOLOGY_INVALID")
        if self.data_quality not in QUALITY or not self.explanation or not self.evidence:
            raise ValueError(f"{type(self).__name__}_CONTRACT_INVALID")
        if self.policy_id != "V28_MARKET_INTELLIGENCE_POLICY" or self.policy_version != "1.0.0":
            raise ValueError(f"{type(self).__name__}_POLICY_INVALID")
        evidence = dict(self.evidence)
        identity_payload = {"context": type(self).__name__, "policy_id": self.policy_id,
                            "policy_version": self.policy_version, "evidence": _plain(evidence)}
        evidence["evidence_id"] = sha256(json.dumps(identity_payload, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        object.__setattr__(self, "evidence", _freeze(evidence))


@dataclass(frozen=True)
class StructureContext(ContextBase):
    ALLOWED = frozenset({"ADVANCING", "DECLINING", "RANGE", "EXPANSION", "UNDETERMINED"})


@dataclass(frozen=True)
class RegimeContext(ContextBase):
    ALLOWED = frozenset({"TREND", "RANGE", "TRANSITION", "EXPANSION", "VOLATILITY_SHIFT", "UNDETERMINED"})


@dataclass(frozen=True)
class TrendContext(ContextBase):
    ALLOWED = frozenset({"UPWARD", "DOWNWARD", "SIDEWAYS", "UNDETERMINED"})


@dataclass(frozen=True)
class MomentumContext(ContextBase):
    ALLOWED = frozenset({"ACCELERATION", "DECELERATION", "CONTINUATION", "IMPULSE", "WEAKENING", "UNDETERMINED"})


@dataclass(frozen=True)
class VolatilityContext(ContextBase):
    ALLOWED = frozenset({"STABLE", "SHIFT", "UNDETERMINED"})


@dataclass(frozen=True)
class LiquidityContext(ContextBase):
    ALLOWED = frozenset({"OBSERVED_GEOMETRY", "HYPOTHESIS", "UNDETERMINED"})


@dataclass(frozen=True)
class OpportunityContext(ContextBase):
    ALLOWED = frozenset({"PRESENT", "ABSENT", "UNDETERMINED"})


CONTEXT_TYPES = (StructureContext, RegimeContext, TrendContext, MomentumContext,
                 VolatilityContext, LiquidityContext, OpportunityContext)
