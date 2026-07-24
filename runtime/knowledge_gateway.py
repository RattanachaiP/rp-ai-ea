"""Fail-closed anti-corruption boundary from Knowledge OS to Runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from threading import RLock
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable

from learning.common.immutable import freeze, thaw

GATEWAY_CONTRACT_VERSION = "1.0.0"
COMPATIBILITY_POLICY_VERSION = "1.0.0"
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _major(version: object) -> int | None:
    if not isinstance(version, str):
        return None
    match = _SEMVER.fullmatch(version)
    return int(match.group(1)) if match else None


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@runtime_checkable
class ActiveKnowledgeReader(Protocol):
    """Minimal Knowledge OS read port accepted by Runtime."""

    def list_active(self) -> tuple[Any, ...]: ...


@dataclass(frozen=True)
class RuntimeKnowledgeDescriptor:
    """Runtime-owned immutable DTO; no Registry implementation object crosses the boundary."""

    knowledge_uuid: str
    activation_uuid: str
    semantic_identity: str
    sequence: int
    schema_version: str
    configuration_version: str
    activated_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_uuid": self.knowledge_uuid,
            "activation_uuid": self.activation_uuid,
            "semantic_identity": self.semantic_identity,
            "sequence": self.sequence,
            "schema_version": self.schema_version,
            "configuration_version": self.configuration_version,
            "activated_at": self.activated_at,
            "metadata": thaw(self.metadata),
        }


@dataclass(frozen=True)
class KnowledgeRuntimeSnapshot:
    snapshot_digest: str
    registry_digest: str
    gateway_contract_version: str
    compatibility_policy_version: str
    supported_schema_majors: tuple[int, ...]
    supported_configuration_majors: tuple[int, ...]
    highest_registry_sequence: int
    source_event_count: int
    generated_at: str
    entries: tuple[RuntimeKnowledgeDescriptor, ...]
    rejected: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rejected", freeze(dict(self.rejected)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_digest": self.snapshot_digest,
            "registry_digest": self.registry_digest,
            "gateway_contract_version": self.gateway_contract_version,
            "compatibility_policy_version": self.compatibility_policy_version,
            "supported_schema_majors": list(self.supported_schema_majors),
            "supported_configuration_majors": list(self.supported_configuration_majors),
            "highest_registry_sequence": self.highest_registry_sequence,
            "source_event_count": self.source_event_count,
            "generated_at": self.generated_at,
            "entries": [entry.to_dict() for entry in self.entries],
            "rejected": thaw(self.rejected),
        }


class KnowledgeRuntimeGateway:
    """Sole Runtime read boundary for compatible ACTIVE Knowledge."""

    def __init__(
        self,
        registry: ActiveKnowledgeReader,
        *,
        supported_schema_majors: Iterable[int] = (1,),
        supported_configuration_majors: Iterable[int] = (1,),
        clock=_generated_at,
    ) -> None:
        if not isinstance(registry, ActiveKnowledgeReader):
            raise TypeError("ACTIVE_KNOWLEDGE_READER_REQUIRED")
        self._schema_majors = self._validate_majors(supported_schema_majors)
        self._configuration_majors = self._validate_majors(supported_configuration_majors)
        self._registry = registry
        self._clock = clock
        self._lock = RLock()
        self._cached_registry_digest = ""
        self._cached_snapshot: KnowledgeRuntimeSnapshot | None = None
        self._highest_sequence_seen = 0

    @staticmethod
    def _validate_majors(values: Iterable[int]) -> tuple[int, ...]:
        try:
            result = tuple(sorted(set(values)))
        except TypeError as exc:
            raise ValueError("INVALID_COMPATIBILITY_CONFIGURATION") from exc
        if not result or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in result):
            raise ValueError("INVALID_COMPATIBILITY_CONFIGURATION")
        return result

    def _compatibility_error(self, entry: Any) -> str | None:
        schema = _major(getattr(entry, "schema_version", None))
        configuration = _major(getattr(entry, "configuration_version", None))
        if schema not in self._schema_majors:
            return "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"
        if configuration not in self._configuration_majors:
            return "UNSUPPORTED_KNOWLEDGE_CONFIGURATION_VERSION"
        return None

    @staticmethod
    def _validate_projection(active: tuple[Any, ...]) -> int:
        knowledge_ids: set[str] = set()
        semantic_ids: set[str] = set()
        activation_ids: set[str] = set()
        sequences: set[int] = set()
        highest = 0
        required = (
            "knowledge_uuid", "activation_uuid", "semantic_identity", "sequence",
            "schema_version", "configuration_version", "activation_timestamp", "metadata",
        )
        for entry in active:
            if any(not hasattr(entry, name) for name in required) or getattr(entry, "status", None) != "ACTIVE":
                raise RuntimeError("RUNTIME_KNOWLEDGE_PROJECTION_INVALID")
            knowledge = entry.knowledge_uuid
            semantic = entry.semantic_identity
            activation = entry.activation_uuid
            sequence = entry.sequence
            if (
                not all(isinstance(value, str) and value.strip() for value in (knowledge, semantic, activation))
                or not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1
                or knowledge in knowledge_ids or semantic in semantic_ids
                or activation in activation_ids or sequence in sequences
            ):
                raise RuntimeError("RUNTIME_KNOWLEDGE_PROJECTION_INVALID")
            knowledge_ids.add(knowledge)
            semantic_ids.add(semantic)
            activation_ids.add(activation)
            sequences.add(sequence)
            highest = max(highest, sequence)
        return highest

    @staticmethod
    def _descriptor(entry: Any) -> RuntimeKnowledgeDescriptor:
        return RuntimeKnowledgeDescriptor(
            knowledge_uuid=entry.knowledge_uuid,
            activation_uuid=entry.activation_uuid,
            semantic_identity=entry.semantic_identity,
            sequence=entry.sequence,
            schema_version=entry.schema_version,
            configuration_version=entry.configuration_version,
            activated_at=entry.activation_timestamp,
            metadata=entry.metadata,
        )

    def _read(self) -> KnowledgeRuntimeSnapshot:
        # Deliberately replay on every read: corruption must propagate and stale
        # snapshots must never be served. Cache preserves immutable object identity only.
        active = tuple(self._registry.list_active())
        highest_sequence = self._validate_projection(active)
        with self._lock:
            if highest_sequence < self._highest_sequence_seen:
                raise RuntimeError("ACTIVE_KNOWLEDGE_REGISTRY_ROLLBACK_DETECTED")
            registry_body = [entry.to_dict() for entry in active]
            registry_digest = sha256(_canonical(registry_body).encode("utf-8")).hexdigest()
            if self._cached_snapshot is not None and self._cached_registry_digest == registry_digest:
                return self._cached_snapshot

            accepted: list[RuntimeKnowledgeDescriptor] = []
            rejected: dict[str, str] = {}
            for entry in active:
                reason = self._compatibility_error(entry)
                if reason is None:
                    accepted.append(self._descriptor(entry))
                else:
                    rejected[entry.knowledge_uuid] = reason
            accepted.sort(key=lambda item: (item.semantic_identity, item.knowledge_uuid))
            policy = {
                "gateway_contract_version": GATEWAY_CONTRACT_VERSION,
                "compatibility_policy_version": COMPATIBILITY_POLICY_VERSION,
                "supported_schema_majors": self._schema_majors,
                "supported_configuration_majors": self._configuration_majors,
            }
            body = {
                "registry_digest": registry_digest,
                "policy": policy,
                "highest_registry_sequence": highest_sequence,
                "source_event_count": len(active),
                "entries": [item.to_dict() for item in accepted],
                "rejected": rejected,
            }
            snapshot = KnowledgeRuntimeSnapshot(
                snapshot_digest=sha256(_canonical(body).encode("utf-8")).hexdigest(),
                registry_digest=registry_digest,
                gateway_contract_version=GATEWAY_CONTRACT_VERSION,
                compatibility_policy_version=COMPATIBILITY_POLICY_VERSION,
                supported_schema_majors=self._schema_majors,
                supported_configuration_majors=self._configuration_majors,
                highest_registry_sequence=highest_sequence,
                source_event_count=len(active),
                generated_at=self._clock(),
                entries=tuple(accepted),
                rejected=rejected,
            )
            self._highest_sequence_seen = highest_sequence
            self._cached_registry_digest = registry_digest
            self._cached_snapshot = snapshot
            return snapshot

    def snapshot(self) -> KnowledgeRuntimeSnapshot:
        return self._read()

    def get_snapshot(self) -> KnowledgeRuntimeSnapshot:
        return self.snapshot()

    def list_active(self) -> tuple[RuntimeKnowledgeDescriptor, ...]:
        return self._read().entries

    def get_active(self, knowledge_uuid: str) -> RuntimeKnowledgeDescriptor | None:
        return next((item for item in self._read().entries if item.knowledge_uuid == knowledge_uuid), None)

    def resolve(self, semantic_identity: str) -> RuntimeKnowledgeDescriptor | None:
        return next((item for item in self._read().entries if item.semantic_identity == semantic_identity), None)

    def lookup(self, value: str) -> RuntimeKnowledgeDescriptor | None:
        return self.get_active(value) or self.resolve(value)
