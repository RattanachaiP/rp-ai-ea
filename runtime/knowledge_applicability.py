"""Deterministic, stateless selection of applicable Runtime Knowledge."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid5

from learning.common.immutable import freeze, thaw
from runtime.knowledge_gateway import KnowledgeRuntimeSnapshot, RuntimeKnowledgeDescriptor

_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MATCH_FIELDS = (
    ("SYMBOL", "symbol", "symbols"), ("SESSION", "session", "sessions"),
    ("TIMEFRAME", "timeframe", "timeframes"), ("REGIME", "market_regime", "market_regimes"),
    ("VOLATILITY", "volatility_class", "volatility_classes"),
    ("TREND_STATE", "trend_state", "trend_states"),
    ("EXECUTION_PROFILE", "execution_profile", "execution_profiles"),
)


def canonical_digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)
    return value.strip().upper()


def _values(value: object, code: str, allow_empty: bool = False) -> tuple[str, ...]:
    if value is None and allow_empty:
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(code)
    result = tuple(sorted({_text(item, code) for item in value}))
    if not result and not allow_empty:
        raise ValueError(code)
    if "*" in result and len(result) != 1:
        raise ValueError(code)
    return result


def _major(version: object) -> int | None:
    match = _SEMVER.fullmatch(version) if isinstance(version, str) else None
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class RuntimeContext:
    symbol: str; timeframe: str; session: str; market_regime: str; volatility_class: str
    trend_state: str; execution_profile: str; runtime_version: str; feature_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("symbol", "timeframe", "session", "market_regime", "volatility_class", "trend_state", "execution_profile"):
            object.__setattr__(self, name, _text(getattr(self, name), f"INVALID_RUNTIME_{name.upper()}"))
        if _major(self.runtime_version) is None:
            raise ValueError("INVALID_RUNTIME_VERSION")
        object.__setattr__(self, "feature_flags", _values(self.feature_flags, "INVALID_RUNTIME_FEATURE_FLAGS", True))


@dataclass(frozen=True)
class ApplicableKnowledge:
    knowledge_uuid: str; semantic_identity: str; specificity_score: float; priority: int; confidence: float
    matching_factors: tuple[str, ...]; reason_codes: tuple[str, ...]; snapshot_digest: str; registry_sequence: int
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if (not isinstance(self.knowledge_uuid, str) or not self.knowledge_uuid or
            not isinstance(self.semantic_identity, str) or not self.semantic_identity or
            not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority < 0 or
            not isinstance(self.registry_sequence, int) or isinstance(self.registry_sequence, bool) or self.registry_sequence < 1 or
            isinstance(self.specificity_score, bool) or not isinstance(self.specificity_score, (int, float)) or
            not isfinite(self.specificity_score) or not 0 <= self.specificity_score <= 1 or
            isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or
            not isfinite(self.confidence) or not 0 <= self.confidence <= 1 or
            not isinstance(self.snapshot_digest, str) or not _HEX64.fullmatch(self.snapshot_digest)):
            raise ValueError("INVALID_APPLICABLE_KNOWLEDGE")
        object.__setattr__(self, "specificity_score", float(self.specificity_score))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_uuid": self.knowledge_uuid, "semantic_identity": self.semantic_identity,
            "specificity_score": self.specificity_score, "priority": self.priority, "confidence": self.confidence,
            "matching_factors": list(self.matching_factors), "reason_codes": list(self.reason_codes),
            "snapshot_digest": self.snapshot_digest, "registry_sequence": self.registry_sequence,
            "metadata": thaw(self.metadata),
        }


@dataclass(frozen=True)
class ApplicabilityReport:
    snapshot_digest: str; context: RuntimeContext; applicable: tuple[ApplicableKnowledge, ...]
    rejected: tuple[tuple[str, tuple[str, ...]], ...]; confidence: float; report_digest: str = ""; report_uuid: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_digest, str) or not _HEX64.fullmatch(self.snapshot_digest) or not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("INVALID_APPLICABILITY_REPORT")
        body = {"snapshot_digest": self.snapshot_digest, "context": asdict(self.context),
                "applicable": [item.to_dict() for item in self.applicable],
                "rejected": [[key, list(codes)] for key, codes in self.rejected], "confidence": float(self.confidence)}
        digest = canonical_digest(body)
        identifier = str(uuid5(NAMESPACE_URL, f"applicability:{digest}"))
        if self.report_digest and self.report_digest != digest:
            raise ValueError("APPLICABILITY_REPORT_DIGEST_MISMATCH")
        if self.report_uuid and self.report_uuid != identifier:
            raise ValueError("APPLICABILITY_REPORT_UUID_MISMATCH")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "report_digest", digest)
        object.__setattr__(self, "report_uuid", identifier)

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_digest": self.snapshot_digest, "context": asdict(self.context),
                "applicable": [item.to_dict() for item in self.applicable],
                "rejected": [[key, list(codes)] for key, codes in self.rejected], "confidence": self.confidence,
                "report_digest": self.report_digest, "report_uuid": self.report_uuid}


@runtime_checkable
class ApplicabilityReportWriter(Protocol):
    def append(self, report: ApplicabilityReport): ...


@dataclass(frozen=True)
class ApplicabilityConfig:
    supported_gateway_contract_majors: tuple[int, ...] = (1,)
    supported_policy_majors: tuple[int, ...] = (1,)
    known_sessions: tuple[str, ...] = ("ASIA", "LONDON", "NEW_YORK")
    known_regimes: tuple[str, ...] = ("RANGE", "TREND", "TRANSITION")

    def __post_init__(self) -> None:
        for name in ("supported_gateway_contract_majors", "supported_policy_majors"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not values or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in values):
                raise ValueError("INVALID_APPLICABILITY_CONFIGURATION")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        object.__setattr__(self, "known_sessions", _values(self.known_sessions, "INVALID_KNOWN_SESSIONS"))
        object.__setattr__(self, "known_regimes", _values(self.known_regimes, "INVALID_KNOWN_REGIMES"))


class ApplicabilityEvaluationError(ValueError): pass


class KnowledgeApplicabilityEngine:
    """Pure Runtime evaluator with no registry access or last-report state."""
    def __init__(self, config: ApplicabilityConfig = ApplicabilityConfig(), report_writer: ApplicabilityReportWriter | None = None):
        if not isinstance(config, ApplicabilityConfig): raise TypeError("APPLICABILITY_CONFIG_REQUIRED")
        if report_writer is not None and not isinstance(report_writer, ApplicabilityReportWriter): raise TypeError("APPLICABILITY_REPORT_WRITER_REQUIRED")
        self.config, self._writer = config, report_writer

    def evaluate(self, snapshot: KnowledgeRuntimeSnapshot, context: RuntimeContext) -> ApplicabilityReport:
        self._validate_snapshot(snapshot, context)
        candidates = [self._candidate(entry) for entry in snapshot.entries]
        self._validate_candidates(candidates)
        accepted, rejected = [], []
        for candidate in sorted(candidates, key=lambda item: (item["semantic_identity"], item["knowledge_uuid"])):
            codes, factors, specificity = self._match(candidate, context)
            if any(code.endswith("_MISMATCH") or code.startswith("UNSUPPORTED_") or code == "FEATURE_MISMATCH" for code in codes):
                rejected.append((candidate["knowledge_uuid"], tuple(codes))); continue
            accepted.append(ApplicableKnowledge(candidate["knowledge_uuid"], candidate["semantic_identity"], specificity,
                candidate["priority"], candidate["confidence"], tuple(factors), tuple(codes), snapshot.snapshot_digest,
                candidate["registry_sequence"], candidate["metadata"]))
        winners = {}
        for item in accepted:
            old = winners.get(item.semantic_identity)
            rank = (-item.priority, -item.specificity_score, -item.confidence, item.knowledge_uuid)
            if old is None or rank < (-old.priority, -old.specificity_score, -old.confidence, old.knowledge_uuid): winners[item.semantic_identity] = item
        for item in accepted:
            if winners[item.semantic_identity] != item: rejected.append((item.knowledge_uuid, item.reason_codes + ("CONFLICT_SUPERSEDED",)))
        selected = tuple(sorted(winners.values(), key=lambda x: (-x.priority, -x.specificity_score, -x.confidence, x.semantic_identity, x.knowledge_uuid)))
        weight = sum(x.specificity_score for x in selected)
        confidence = sum(x.confidence * x.specificity_score for x in selected) / weight if weight else 0.0
        report = ApplicabilityReport(snapshot.snapshot_digest, context, selected, tuple(sorted(rejected)), confidence)
        if self._writer is not None: self._writer.append(report)
        return report

    def resolve(self, snapshot: KnowledgeRuntimeSnapshot, context: RuntimeContext) -> tuple[ApplicableKnowledge, ...]:
        return self.evaluate(snapshot, context).applicable

    def _validate_snapshot(self, snapshot, context) -> None:
        if not isinstance(snapshot, KnowledgeRuntimeSnapshot): raise ApplicabilityEvaluationError("KNOWLEDGE_RUNTIME_SNAPSHOT_REQUIRED")
        if not isinstance(context, RuntimeContext): raise ApplicabilityEvaluationError("INVALID_RUNTIME_CONTEXT")
        if not _HEX64.fullmatch(snapshot.snapshot_digest): raise ApplicabilityEvaluationError("INVALID_SNAPSHOT_DIGEST")
        if _major(snapshot.gateway_contract_version) not in self.config.supported_gateway_contract_majors: raise ApplicabilityEvaluationError("UNSUPPORTED_GATEWAY_CONTRACT_VERSION")
        if _major(snapshot.compatibility_policy_version) not in self.config.supported_policy_majors: raise ApplicabilityEvaluationError("UNSUPPORTED_COMPATIBILITY_POLICY_VERSION")
        if context.session not in self.config.known_sessions: raise ApplicabilityEvaluationError("UNKNOWN_SESSION")
        if context.market_regime not in self.config.known_regimes: raise ApplicabilityEvaluationError("UNKNOWN_REGIME")

    @staticmethod
    def _candidate(entry: RuntimeKnowledgeDescriptor) -> dict[str, Any]:
        metadata = thaw(entry.metadata)
        try:
            versions = _values(metadata.get("supported_runtime_versions", ("*",)), "INVALID_SUPPORTED_RUNTIME_VERSIONS")
            if versions != ("*",) and any(_major(value) is None for value in versions): raise ValueError("INVALID_SUPPORTED_RUNTIME_VERSIONS")
            return {"knowledge_uuid": entry.knowledge_uuid, "semantic_identity": entry.semantic_identity, "registry_sequence": entry.sequence,
                "supported_runtime_versions": versions, "required_features": _values(metadata.get("required_features", ()), "INVALID_REQUIRED_FEATURES", True),
                "symbols": _values(metadata.get("symbols", ("*",)), "INVALID_SYMBOLS"), "sessions": _values(metadata.get("sessions", ("*",)), "INVALID_SESSIONS"),
                "timeframes": _values(metadata.get("timeframes", ("*",)), "INVALID_TIMEFRAMES"), "market_regimes": _values(metadata.get("market_regimes", ("*",)), "INVALID_MARKET_REGIMES"),
                "volatility_classes": _values(metadata.get("volatility_classes", ("*",)), "INVALID_VOLATILITY_CLASSES"), "trend_states": _values(metadata.get("trend_states", ("*",)), "INVALID_TREND_STATES"),
                "execution_profiles": _values(metadata.get("execution_profiles", ("*",)), "INVALID_EXECUTION_PROFILES"),
                "priority": metadata.get("priority", 0), "confidence": metadata.get("confidence", 1.0), "metadata": metadata}
        except ValueError as exc: raise ApplicabilityEvaluationError(str(exc)) from exc

    @staticmethod
    def _validate_candidates(candidates) -> None:
        knowledge, sequences, identities = set(), set(), set()
        for item in candidates:
            priority, confidence = item["priority"], item["confidence"]
            if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0 or isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not isfinite(confidence) or not 0 <= confidence <= 1:
                raise ApplicabilityEvaluationError("INVALID_APPLICABILITY_CANDIDATE")
            identity = (item["semantic_identity"], item["registry_sequence"])
            if item["knowledge_uuid"] in knowledge or item["registry_sequence"] in sequences or identity in identities: raise ApplicabilityEvaluationError("DUPLICATE_APPLICABILITY_CANDIDATE")
            knowledge.add(item["knowledge_uuid"]); sequences.add(item["registry_sequence"]); identities.add(identity)

    @staticmethod
    def _match(item, context):
        codes, factors, exact = [], [], 0
        for label, context_name, candidate_name in _MATCH_FIELDS:
            allowed, value = item[candidate_name], getattr(context, context_name)
            if allowed == ("*",): codes.append(f"{label}_WILDCARD")
            elif value in allowed: codes.append(f"{label}_MATCH"); factors.append(f"{label}_MATCH"); exact += 1
            else: codes.append(f"{label}_MISMATCH")
        versions = item["supported_runtime_versions"]
        if versions == ("*",): codes.append("RUNTIME_VERSION_WILDCARD")
        elif context.runtime_version in versions: codes.append("RUNTIME_VERSION_MATCH"); factors.append("RUNTIME_VERSION_MATCH"); exact += 1
        else: codes.append("UNSUPPORTED_RUNTIME_VERSION")
        codes.append("FEATURE_MATCH" if set(item["required_features"]).issubset(context.feature_flags) else "FEATURE_MISMATCH")
        return codes, factors, exact / float(len(_MATCH_FIELDS) + 1)
