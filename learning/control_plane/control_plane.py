"""Deterministic, read-only coordination for Knowledge subsystems.

This module intentionally contains no promotion, retirement, policy execution,
or persistence operations.  It only reads already-published subsystem records.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from learning.analytics import AnalyticsRepository
from learning.governance import GOVERNANCE_SCHEMA_VERSION, GovernanceRepository
from learning.knowledge import KnowledgeRepository
from learning.knowledge.schema import KNOWLEDGE_VERSION
from learning.lifecycle import LIFECYCLE_SCHEMA_VERSION, LifecycleRepository


class SubsystemHealth(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


_SUBSYSTEMS = ("analytics", "governance", "lifecycle", "policy", "repository")


def _canonical(value: Any) -> Any:
    """Convert published values to JSON-compatible, deterministically ordered data."""
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        # Published repositories already define sequence order (notably the
        # lifecycle timeline's replay order), which must not be rewritten.
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        values = [_canonical(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    return value


@dataclass(frozen=True)
class _Observation:
    status: SubsystemHealth
    value: Any = None
    error: str | None = None


class KnowledgeControlPlane:
    """Coordinates read-only views of Knowledge subsystems without authority.

    Providers are dependency-injected to preserve subsystem isolation.  A
    policy provider is optional because policy ownership remains external to
    this coordination layer; its absence is reported as ``UNKNOWN``.
    """

    def __init__(
        self,
        root: str = "learning_data",
        *,
        knowledge_repository: Any | None = None,
        governance_repository: Any | None = None,
        lifecycle_repository: Any | None = None,
        analytics_repository: Any | None = None,
        policy_provider: Any | None = None,
        repository_version: str = "1.0",
        policy_schema_version: str | None = None,
        policy_configuration_version: str | None = None,
    ) -> None:
        self._knowledge = knowledge_repository or KnowledgeRepository(root)
        self._governance = governance_repository or GovernanceRepository(root)
        self._lifecycle = lifecycle_repository or LifecycleRepository(root)
        self._analytics = analytics_repository or AnalyticsRepository(root)
        self._policy = policy_provider
        self._repository_version = repository_version
        self._policy_schema_version = policy_schema_version
        self._policy_configuration_version = policy_configuration_version

    @staticmethod
    def _read(call: Callable[[], Any], *, unknown: bool = False) -> _Observation:
        if unknown:
            return _Observation(SubsystemHealth.UNKNOWN)
        try:
            value = call()
        except FileNotFoundError:
            return _Observation(SubsystemHealth.DEGRADED, error="NOT_FOUND")
        except Exception as error:  # Failures are reported, never repaired.
            return _Observation(SubsystemHealth.FAILED, error=type(error).__name__)
        return _Observation(SubsystemHealth.READY, _canonical(value))

    def _policy_read(self, knowledge_uuid: str | None = None) -> _Observation:
        if self._policy is None:
            return self._read(lambda: None, unknown=True)
        method = getattr(self._policy, "get_policy_result", None) or getattr(self._policy, "load", None)
        if method is None:
            return _Observation(SubsystemHealth.FAILED, error="POLICY_PROVIDER_UNSUPPORTED")
        return self._read(lambda: method(knowledge_uuid) if knowledge_uuid is not None else method())

    def get_knowledge(self, knowledge_uuid: str) -> dict[str, Any] | None:
        observation = self._read(lambda: self._knowledge.load(knowledge_uuid))
        return observation.value if observation.status is SubsystemHealth.READY else None

    def get_governance(self, knowledge_uuid: str) -> dict[str, Any] | None:
        observation = self._read(lambda: self._governance.load(knowledge_uuid))
        return observation.value if observation.status is SubsystemHealth.READY else None

    def get_lifecycle(self, knowledge_uuid: str) -> tuple[dict[str, Any], ...]:
        observation = self._read(lambda: self._lifecycle.timeline(knowledge_uuid))
        return tuple(observation.value or ()) if observation.status is SubsystemHealth.READY else ()

    def get_analytics(self) -> dict[str, Any] | None:
        observation = self._read(self._analytics.latest)
        return observation.value if observation.status is SubsystemHealth.READY else None

    def get_policy_result(self, knowledge_uuid: str | None = None) -> Any | None:
        observation = self._policy_read(knowledge_uuid)
        return observation.value if observation.status is SubsystemHealth.READY else None

    def get_lineage(self, knowledge_uuid: str) -> dict[str, Any]:
        knowledge = self.get_knowledge(knowledge_uuid)
        governance = self.get_governance(knowledge_uuid)
        lineage: dict[str, Any] = {"knowledge_uuid": knowledge_uuid}
        if knowledge:
            lineage.update({key: knowledge[key] for key in ("pattern_uuid", "validation_uuid", "knowledge_version")})
        if governance:
            lineage.update({key: governance[key] for key in ("analytics_uuid", "lineage_reference", "source_baseline_commit")})
        return _canonical(lineage)

    def get_health(self) -> dict[str, Any]:
        observations = {
            "repository": self._read(lambda: self._knowledge.query()),
            "governance": self._read(lambda: self._governance.query()),
            "lifecycle": self._read(lambda: self._lifecycle.storage.all()),
            "analytics": self._read(self._analytics.latest),
            "policy": self._policy_read(),
        }
        statuses = [item.status for item in observations.values()]
        aggregate = (SubsystemHealth.FAILED if SubsystemHealth.FAILED in statuses else
                     SubsystemHealth.DEGRADED if SubsystemHealth.DEGRADED in statuses else
                     SubsystemHealth.READY if SubsystemHealth.READY in statuses else SubsystemHealth.UNKNOWN)
        return {
            "status": aggregate.value,
            "subsystems": {
                name: {"status": observations[name].status.value, **(
                    {"error": observations[name].error} if observations[name].error else {})}
                for name in _SUBSYSTEMS
            },
        }

    def get_status(self) -> dict[str, Any]:
        return {"health": self.get_health(), "capabilities": self.capabilities()}

    def capabilities(self) -> tuple[str, ...]:
        return ("get_analytics", "get_governance", "get_health", "get_knowledge", "get_lifecycle",
                "get_lineage", "get_policy_result", "get_snapshot", "get_status")

    def get_snapshot(self, knowledge_uuid: str | None = None) -> dict[str, Any]:
        """Return a deterministic, non-persistent point-in-time observation."""
        records = self._read(lambda: self._knowledge.query()).value or []
        identifiers = [record["knowledge_uuid"] for record in records]
        if knowledge_uuid is not None:
            identifiers = [knowledge_uuid]
        entries = []
        for identifier in sorted(identifiers):
            entries.append({
                "governance": self.get_governance(identifier),
                "knowledge": self.get_knowledge(identifier),
                "lifecycle": self.get_lifecycle(identifier),
                "lineage": self.get_lineage(identifier),
                "policy_evaluation": self.get_policy_result(identifier),
            })
        analytics = self.get_analytics()
        snapshot = {
            "analytics_summary": analytics,
            "configuration_versions": {
                "analytics": analytics.get("configuration_version") if analytics else None,
                "policy": self._policy_configuration_version,
            },
            "health": self.get_health(),
            "knowledge": entries,
            "repository_version": self._repository_version,
            "schema_versions": {
                "analytics": analytics.get("analytics_version") if analytics else None,
                "governance": GOVERNANCE_SCHEMA_VERSION,
                "knowledge": KNOWLEDGE_VERSION,
                "lifecycle": LIFECYCLE_SCHEMA_VERSION,
                "policy": self._policy_schema_version,
            },
        }
        canonical = _canonical(snapshot)
        canonical["snapshot_digest"] = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return canonical
