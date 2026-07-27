"""Integrity boundary from validated market state to Executor-ready package."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Mapping
from uuid import UUID, uuid5

from runtime.market_state_reader import ValidatedMarketState


class GovernedPackageError(ValueError):
    pass


def _uuid(value: str, reason: str) -> str:
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise GovernedPackageError(reason) from exc
    return value


@dataclass(frozen=True, slots=True)
class DecisionContextLineage:
    context_uuid: str
    market_state_uuid: str
    sequence_id: int
    timestamp: str
    symbol: str
    timeframe: str
    producer: str

    @classmethod
    def from_market_state(cls, state: ValidatedMarketState):
        if type(state) is not ValidatedMarketState:
            raise GovernedPackageError("UNVALIDATED_MARKET_STATE")
        uid = str(uuid5(UUID(state.market_state_uuid), "decision-context"))
        return cls(uid, state.market_state_uuid, state.sequence_id, state.timestamp,
                   state.symbol, state.timeframe, state.producer)


@dataclass(frozen=True, slots=True)
class GovernedRecommendation:
    decision_uuid: str
    context_uuid: str
    intelligence_uuid: str
    activation_uuid: str
    confidence: float
    direction: str
    risk_profile: str
    governance_metadata: Mapping[str, str]
    timestamp: str

    def __post_init__(self):
        for name in ("decision_uuid", "context_uuid", "intelligence_uuid", "activation_uuid"):
            _uuid(getattr(self, name), "INCOMPLETE_RECOMMENDATION")
        if (type(self.confidence) is not float or not 0 <= self.confidence <= 1 or
                self.direction not in {"BUY", "SELL", "HOLD"} or
                not isinstance(self.risk_profile, str) or not self.risk_profile.strip() or
                not isinstance(self.governance_metadata, Mapping) or
                not self.governance_metadata):
            raise GovernedPackageError("INCOMPLETE_RECOMMENDATION")


@dataclass(frozen=True, slots=True)
class GovernedExecutionPackage:
    package_uuid: str
    parent_uuid: str
    recommendation_uuid: str
    readiness_uuid: str
    environment_uuid: str
    feasibility_uuid: str
    activation_uuid: str
    timestamp: str
    repository_digest: str
    snapshot_digest: str

    def diagnostics(self) -> str:
        return "\n".join(("[PACKAGE]", f"UUID={self.package_uuid}",
            f"Recommendation UUID={self.recommendation_uuid}",
            f"Readiness UUID={self.readiness_uuid}",
            f"Environment UUID={self.environment_uuid}",
            f"Feasibility UUID={self.feasibility_uuid}",
            f"Digest={self.repository_digest}", "Status=READY"))


class ExecutionPackageBuilder:
    """Build and validate a single immutable activation lineage."""

    @staticmethod
    def build(*, recommendation: GovernedRecommendation, parent_uuid: str,
              readiness_uuid: str, environment_uuid: str, feasibility_uuid: str,
              repository_digest: str, snapshot_digest: str,
              readiness_timestamp: str, environment_timestamp: str,
              feasibility_timestamp: str) -> GovernedExecutionPackage:
        if type(recommendation) is not GovernedRecommendation:
            raise GovernedPackageError("INCOMPLETE_RECOMMENDATION")
        identities = (parent_uuid, recommendation.decision_uuid, readiness_uuid,
                      environment_uuid, feasibility_uuid, recommendation.activation_uuid)
        for value in identities:
            _uuid(value, "MISSING_PACKAGE_IDENTITY")
        if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
               for value in (repository_digest, snapshot_digest)):
            raise GovernedPackageError("DIGEST_MISMATCH")
        try:
            times = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in
                     (recommendation.timestamp, readiness_timestamp,
                      environment_timestamp, feasibility_timestamp)]
        except (ValueError, AttributeError) as exc:
            raise GovernedPackageError("INVALID_TIMESTAMP") from exc
        if times != sorted(times):
            raise GovernedPackageError("TIMESTAMP_ORDERING")
        payload = {"parent_uuid": parent_uuid,
            "recommendation_uuid": recommendation.decision_uuid,
            "readiness_uuid": readiness_uuid, "environment_uuid": environment_uuid,
            "feasibility_uuid": feasibility_uuid,
            "activation_uuid": recommendation.activation_uuid,
            "timestamp": feasibility_timestamp, "repository_digest": repository_digest,
            "snapshot_digest": snapshot_digest}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        uid = str(uuid5(UUID(parent_uuid), hashlib.sha256(canonical.encode()).hexdigest()))
        return GovernedExecutionPackage(uid, **payload)

    @staticmethod
    def validate(package: GovernedExecutionPackage, *, expected_parent_uuid: str,
                 expected_repository_digest: str, expected_snapshot_digest: str,
                 expected_activation_uuid: str) -> None:
        if type(package) is not GovernedExecutionPackage:
            raise GovernedPackageError("INVALID_PACKAGE")
        for field in fields(package):
            if getattr(package, field.name) in (None, ""):
                raise GovernedPackageError("MISSING_PACKAGE_IDENTITY")
        if package.parent_uuid != expected_parent_uuid:
            raise GovernedPackageError("UUID_LINEAGE_BREAK")
        if package.activation_uuid != expected_activation_uuid:
            raise GovernedPackageError("MULTIPLE_ACTIVATION_LINEAGE")
        if package.repository_digest != expected_repository_digest:
            raise GovernedPackageError("DIGEST_MISMATCH")
        if package.snapshot_digest != expected_snapshot_digest:
            raise GovernedPackageError("SNAPSHOT_MISMATCH")
