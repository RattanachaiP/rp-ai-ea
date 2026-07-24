"""Deterministic, read-only coordination for Knowledge subsystems."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

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


@runtime_checkable
class PolicyResultProvider(Protocol):
    """Explicit read-only provider contract for published policy results."""

    def get_policy_result(self, knowledge_uuid: str | None = None) -> Any:
        ...


_SUBSYSTEMS = ("analytics", "governance", "lifecycle", "policy", "repository")
_ERROR_CODES = {
    FileNotFoundError: "NOT_FOUND",
    PermissionError: "PERMISSION_DENIED",
    json.JSONDecodeError: "CORRUPT_RECORD",
    KeyError: "SCHEMA_MISMATCH",
    ValueError: "INVALID_RECORD",
}


def _canonical(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
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

    def public(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status.value}
        if self.status is SubsystemHealth.READY:
            result["value"] = self.value
        if self.error:
            result["error"] = self.error
        return result


class KnowledgeControlPlane:
    """Read-only coordination surface with fail-closed snapshot semantics."""

    def __init__(
        self,
        root: str = "learning_data",
        *,
        knowledge_repository: Any | None = None,
        governance_repository: Any | None = None,
        lifecycle_repository: Any | None = None,
        analytics_repository: Any | None = None,
        policy_provider: PolicyResultProvider | None = None,
        repository_version: str = "1.0",
        policy_schema_version: str | None = None,
        policy_configuration_version: str | None = None,
    ) -> None:
        self._knowledge = knowledge_repository if knowledge_repository is not None else KnowledgeRepository(root)
        self._governance = governance_repository if governance_repository is not None else GovernanceRepository(root)
        self._lifecycle = lifecycle_repository if lifecycle_repository is not None else LifecycleRepository(root)
        self._analytics = analytics_repository if analytics_repository is not None else AnalyticsRepository(root)
        if policy_provider is not None and not isinstance(policy_provider, PolicyResultProvider):
            raise TypeError("POLICY_PROVIDER_UNSUPPORTED")
        self._policy = policy_provider
        self._repository_version = repository_version
        self._policy_schema_version = policy_schema_version
        self._policy_configuration_version = policy_configuration_version

    @staticmethod
    def _error_code(error: Exception) -> str:
        for error_type, code in _ERROR_CODES.items():
            if isinstance(error, error_type):
                return code
        return "PROVIDER_FAILURE"

    @classmethod
    def _read(cls, call: Callable[[], Any], *, unknown: bool = False) -> _Observation:
        if unknown:
            return _Observation(SubsystemHealth.UNKNOWN, error="PROVIDER_NOT_CONFIGURED")
        try:
            value = call()
        except Exception as error:
            code = cls._error_code(error)
            status = SubsystemHealth.DEGRADED if code == "NOT_FOUND" else SubsystemHealth.FAILED
            return _Observation(status, error=code)
        if value is None:
            return _Observation(SubsystemHealth.DEGRADED, error="NOT_FOUND")
        return _Observation(SubsystemHealth.READY, _canonical(value))

    def _policy_read(self, knowledge_uuid: str | None = None) -> _Observation:
        if self._policy is None:
            return self._read(lambda: None, unknown=True)
        return self._read(lambda: self._policy.get_policy_result(knowledge_uuid))

    def get_knowledge_observation(self, knowledge_uuid: str) -> dict[str, Any]:
        return self._read(lambda: self._knowledge.load(knowledge_uuid)).public()

    def get_governance_observation(self, knowledge_uuid: str) -> dict[str, Any]:
        return self._read(lambda: self._governance.load(knowledge_uuid)).public()

    def get_lifecycle_observation(self, knowledge_uuid: str) -> dict[str, Any]:
        return self._read(lambda: self._lifecycle.timeline(knowledge_uuid)).public()

    def get_analytics_observation(self) -> dict[str, Any]:
        return self._read(self._analytics.latest).public()

    def get_policy_observation(self, knowledge_uuid: str | None = None) -> dict[str, Any]:
        return self._policy_read(knowledge_uuid).public()

    def get_knowledge(self, knowledge_uuid: str) -> dict[str, Any] | None:
        item = self.get_knowledge_observation(knowledge_uuid)
        return item.get("value") if item["status"] == "READY" else None

    def get_governance(self, knowledge_uuid: str) -> dict[str, Any] | None:
        item = self.get_governance_observation(knowledge_uuid)
        return item.get("value") if item["status"] == "READY" else None

    def get_lifecycle(self, knowledge_uuid: str) -> tuple[dict[str, Any], ...]:
        item = self.get_lifecycle_observation(knowledge_uuid)
        return tuple(item.get("value", ())) if item["status"] == "READY" else ()

    def get_analytics(self) -> dict[str, Any] | None:
        item = self.get_analytics_observation()
        return item.get("value") if item["status"] == "READY" else None

    def get_policy_result(self, knowledge_uuid: str | None = None) -> Any | None:
        item = self.get_policy_observation(knowledge_uuid)
        return item.get("value") if item["status"] == "READY" else None

    @staticmethod
    def _lineage(knowledge_uuid: str, knowledge: _Observation, governance: _Observation) -> _Observation:
        if knowledge.status is not SubsystemHealth.READY:
            return _Observation(knowledge.status, error=knowledge.error)
        if governance.status is not SubsystemHealth.READY:
            return _Observation(governance.status, error=governance.error)
        try:
            lineage = {
                "knowledge_uuid": knowledge_uuid,
                **{key: knowledge.value[key] for key in ("pattern_uuid", "validation_uuid", "knowledge_version")},
                **{key: governance.value[key] for key in ("analytics_uuid", "lineage_reference", "source_baseline_commit")},
            }
        except (KeyError, TypeError):
            return _Observation(SubsystemHealth.FAILED, error="SCHEMA_MISMATCH")
        return _Observation(SubsystemHealth.READY, _canonical(lineage))

    def get_lineage(self, knowledge_uuid: str) -> dict[str, Any]:
        knowledge = self._read(lambda: self._knowledge.load(knowledge_uuid))
        governance = self._read(lambda: self._governance.load(knowledge_uuid))
        result = self._lineage(knowledge_uuid, knowledge, governance)
        if result.status is SubsystemHealth.READY:
            return result.value
        return {"knowledge_uuid": knowledge_uuid, "status": result.status.value, "error": result.error}

    @staticmethod
    def _health_from(observations: Mapping[str, _Observation]) -> dict[str, Any]:
        required_statuses = [observations[name].status for name in ("repository", "governance", "lifecycle", "analytics")]
        if SubsystemHealth.FAILED in required_statuses:
            aggregate = SubsystemHealth.FAILED
        elif SubsystemHealth.DEGRADED in required_statuses:
            aggregate = SubsystemHealth.DEGRADED
        elif all(status is SubsystemHealth.READY for status in required_statuses):
            aggregate = SubsystemHealth.READY
        else:
            aggregate = SubsystemHealth.UNKNOWN
        return {
            "status": aggregate.value,
            "optional_policy_available": observations["policy"].status is SubsystemHealth.READY,
            "subsystems": {
                name: {
                    "status": observations[name].status.value,
                    **({"error": observations[name].error} if observations[name].error else {}),
                }
                for name in _SUBSYSTEMS
            },
        }

    def _lifecycle_health(self, repository: _Observation) -> _Observation:
        if repository.status is not SubsystemHealth.READY:
            return _Observation(repository.status, error=repository.error)
        records = repository.value
        if not isinstance(records, list):
            return _Observation(SubsystemHealth.FAILED, error="SCHEMA_MISMATCH")
        if not records:
            return _Observation(SubsystemHealth.READY, [])
        try:
            knowledge_uuid = records[0]["knowledge_uuid"]
        except (KeyError, TypeError):
            return _Observation(SubsystemHealth.FAILED, error="SCHEMA_MISMATCH")
        return self._read(lambda: self._lifecycle.timeline(knowledge_uuid))

    def _global_observations(self) -> dict[str, _Observation]:
        repository = self._read(lambda: self._knowledge.query())
        return {
            "repository": repository,
            "governance": self._read(lambda: self._governance.query()),
            "lifecycle": self._lifecycle_health(repository),
            "analytics": self._read(self._analytics.latest),
            "policy": self._policy_read(),
        }

    def get_health(self) -> dict[str, Any]:
        return self._health_from(self._global_observations())

    def get_status(self) -> dict[str, Any]:
        return {"health": self.get_health(), "capabilities": self.capabilities()}

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted((
            "get_analytics", "get_analytics_observation", "get_governance", "get_governance_observation",
            "get_health", "get_knowledge", "get_knowledge_observation", "get_lifecycle",
            "get_lifecycle_observation", "get_lineage", "get_policy_observation", "get_policy_result",
            "get_snapshot", "get_status",
        )))

    def get_snapshot(self, knowledge_uuid: str | None = None) -> dict[str, Any]:
        """Read each participating record once and digest the resulting observation set."""
        repository = self._read(lambda: self._knowledge.query())
        analytics = self._read(self._analytics.latest)
        governance_health = self._read(lambda: self._governance.query())
        lifecycle_health = self._lifecycle_health(repository)
        policy_global = self._policy_read()

        identifiers: list[str] = []
        if repository.status is SubsystemHealth.READY:
            try:
                identifiers = [record["knowledge_uuid"] for record in repository.value]
            except (KeyError, TypeError):
                repository = _Observation(SubsystemHealth.FAILED, error="SCHEMA_MISMATCH")
        if knowledge_uuid is not None:
            identifiers = [knowledge_uuid]

        entries: list[dict[str, Any]] = []
        entries_complete = True
        for identifier in sorted(set(identifiers)):
            knowledge = self._read(lambda identifier=identifier: self._knowledge.load(identifier))
            governance = self._read(lambda identifier=identifier: self._governance.load(identifier))
            lifecycle = self._read(lambda identifier=identifier: self._lifecycle.timeline(identifier))
            policy = self._policy_read(identifier)
            lineage = self._lineage(identifier, knowledge, governance)
            observations = {
                "knowledge": knowledge,
                "governance": governance,
                "lifecycle": lifecycle,
                "policy": policy,
                "lineage": lineage,
            }
            complete = all(item.status is SubsystemHealth.READY for item in (knowledge, governance, lifecycle, lineage))
            entries_complete = entries_complete and complete
            entries.append({
                "knowledge_uuid": identifier,
                "status": "COMPLETE" if complete else "INCOMPLETE",
                "observations": {name: observation.public() for name, observation in observations.items()},
            })

        globals_ = {
            "repository": repository,
            "governance": governance_health,
            "lifecycle": lifecycle_health,
            "analytics": analytics,
            "policy": policy_global,
        }
        health = self._health_from(globals_)
        requested_exists = knowledge_uuid is None or bool(entries) and entries[0]["observations"]["knowledge"]["status"] == "READY"
        complete = health["status"] == "READY" and entries_complete and requested_exists
        analytics_value = analytics.value if analytics.status is SubsystemHealth.READY else None
        snapshot = {
            "snapshot_status": "COMPLETE" if complete else "INCOMPLETE",
            "complete": complete,
            "eligible_for_downstream_use": complete,
            "analytics_summary": analytics.public(),
            "configuration_versions": {
                "analytics": analytics_value.get("configuration_version") if isinstance(analytics_value, Mapping) else None,
                "policy": self._policy_configuration_version,
            },
            "health": health,
            "knowledge": entries,
            "repository_version": self._repository_version,
            "schema_versions": {
                "analytics": analytics_value.get("analytics_version") if isinstance(analytics_value, Mapping) else None,
                "governance": GOVERNANCE_SCHEMA_VERSION,
                "knowledge": KNOWLEDGE_VERSION,
                "lifecycle": LIFECYCLE_SCHEMA_VERSION,
                "policy": self._policy_schema_version,
            },
        }
        canonical = _canonical(snapshot)
        canonical["snapshot_digest"] = sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return canonical
