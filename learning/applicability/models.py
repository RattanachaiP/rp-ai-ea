"""Immutable input and output contracts for Knowledge Applicability Engine."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from hashlib import sha256
import json
from math import isfinite
from typing import Mapping
from uuid import NAMESPACE_URL, uuid5
from learning.common.immutable import freeze, thaw


def canonical_digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise ValueError(code)
    return value.strip().upper()


def _texts(value: tuple[str, ...], code: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not value: raise ValueError(code)
    return tuple(sorted({_text(item, code) for item in value}))


@dataclass(frozen=True)
class RuntimeContext:
    symbol: str; timeframe: str; session: str; market_regime: str; volatility_class: str
    trend_state: str; execution_profile: str; runtime_version: str; feature_flags: tuple[str, ...] = ()
    def __post_init__(self):
        for name in ("symbol", "timeframe", "session", "market_regime", "volatility_class", "trend_state", "execution_profile", "runtime_version"):
            object.__setattr__(self, name, _text(getattr(self, name), f"INVALID_RUNTIME_{name.upper()}"))
        if not isinstance(self.feature_flags, tuple) or any(not isinstance(x, str) or not x.strip() for x in self.feature_flags):
            raise ValueError("INVALID_RUNTIME_FEATURE_FLAGS")
        object.__setattr__(self, "feature_flags", tuple(sorted({x.strip().upper() for x in self.feature_flags})))


@dataclass(frozen=True)
class GatewayKnowledge:
    """Gateway projection; registry data is represented only as provenance scalars."""
    knowledge_uuid: str; semantic_identity: str; registry_sequence: int; schema_version: str; configuration_version: str
    supported_runtime_versions: tuple[str, ...]; required_features: tuple[str, ...]
    symbols: tuple[str, ...]; sessions: tuple[str, ...]; timeframes: tuple[str, ...]; market_regimes: tuple[str, ...]; execution_profiles: tuple[str, ...]
    priority: int; confidence: float
    def __post_init__(self):
        if (not isinstance(self.knowledge_uuid, str) or not self.knowledge_uuid or not isinstance(self.semantic_identity, str) or not self.semantic_identity
            or not isinstance(self.registry_sequence, int) or isinstance(self.registry_sequence, bool) or self.registry_sequence < 1
            or not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority < 0
            or isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError("INVALID_GATEWAY_KNOWLEDGE")
        for name in ("schema_version", "configuration_version"):
            object.__setattr__(self, name, _text(getattr(self, name), f"INVALID_{name.upper()}"))
        for name in ("supported_runtime_versions", "required_features", "symbols", "sessions", "timeframes", "market_regimes", "execution_profiles"):
            object.__setattr__(self, name, _texts(getattr(self, name), f"INVALID_{name.upper()}"))
        object.__setattr__(self, "confidence", float(self.confidence))


@dataclass(frozen=True)
class GatewaySnapshot:
    snapshot_uuid: str; snapshot_digest: str; schema_version: str; configuration_version: str; records: tuple[GatewayKnowledge, ...]
    def __post_init__(self):
        if not isinstance(self.snapshot_uuid, str) or not self.snapshot_uuid: raise ValueError("INVALID_GATEWAY_SNAPSHOT")
        if not isinstance(self.snapshot_digest, str) or len(self.snapshot_digest) != 64: raise ValueError("INVALID_GATEWAY_DIGEST")
        object.__setattr__(self, "schema_version", _text(self.schema_version, "INVALID_SNAPSHOT_SCHEMA")); object.__setattr__(self, "configuration_version", _text(self.configuration_version, "INVALID_SNAPSHOT_CONFIGURATION"))
        if not isinstance(self.records, tuple) or any(not isinstance(x, GatewayKnowledge) for x in self.records): raise ValueError("INVALID_GATEWAY_SNAPSHOT")
    def digest_body(self):
        return {"snapshot_uuid": self.snapshot_uuid, "schema_version": self.schema_version, "configuration_version": self.configuration_version, "records": [asdict(x) for x in self.records]}
    def digest_valid(self) -> bool: return canonical_digest(self.digest_body()) == self.snapshot_digest


@dataclass(frozen=True)
class ApplicableKnowledge:
    knowledge_uuid: str; semantic_identity: str; applicability_score: float; priority: int; confidence: float
    matching_factors: tuple[str, ...]; reason_codes: tuple[str, ...]; snapshot_digest: str; registry_sequence: int


@dataclass(frozen=True)
class ApplicabilityReport:
    snapshot_digest: str; context: RuntimeContext; applicable: tuple[ApplicableKnowledge, ...]; rejected: tuple[tuple[str, tuple[str, ...]], ...]
    confidence: float; report_digest: str = ""; report_uuid: str = ""
    def __post_init__(self):
        if not self.report_digest:
            object.__setattr__(self, "report_digest", canonical_digest({"snapshot_digest": self.snapshot_digest, "context": asdict(self.context), "applicable": [asdict(x) for x in self.applicable], "rejected": self.rejected, "confidence": self.confidence}))
        if not self.report_uuid:
            object.__setattr__(self, "report_uuid", str(uuid5(NAMESPACE_URL, f"applicability:{self.report_digest}")))
