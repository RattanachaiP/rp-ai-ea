"""Read-only, fail-closed gateway from Runtime to active Knowledge.

This module is intentionally a boundary adapter.  It neither evaluates Knowledge
nor makes decisions; it only turns the trusted Active Knowledge Registry
projection into immutable, runtime-compatible snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Iterable, Mapping

from learning.active_registry import ActiveKnowledgeEntry, ActiveKnowledgeRegistry
from learning.common.immutable import freeze, thaw


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _major(version: object) -> int | None:
    """Return a strict semantic-version major, accepting optional prereleases."""
    if not isinstance(version, str) or not version:
        return None
    core = version.split("-", 1)[0].split("+", 1)[0].split(".")
    if len(core) != 3 or any(not part.isdecimal() for part in core):
        return None
    return int(core[0])


@dataclass(frozen=True)
class KnowledgeRuntimeSnapshot:
    """An immutable compatible ACTIVE projection supplied to Runtime readers."""

    snapshot_digest: str
    registry_digest: str
    entries: tuple[ActiveKnowledgeEntry, ...]
    rejected: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_digest": self.snapshot_digest,
            "registry_digest": self.registry_digest,
            "entries": [entry.to_dict() for entry in self.entries],
            "rejected": thaw(self.rejected),
        }


class KnowledgeRuntimeGateway:
    """The sole Runtime read boundary for trusted Active Knowledge.

    The registry is injected and remains owned by Knowledge OS.  Registry reads
    are re-verified on every cache refresh by asking its fail-closed projection;
    a read error is deliberately propagated rather than serving stale knowledge.
    """

    def __init__(self, registry: ActiveKnowledgeRegistry, *, supported_schema_majors: Iterable[int] = (1,),
                 supported_configuration_majors: Iterable[int] = (1,)) -> None:
        if not isinstance(registry, ActiveKnowledgeRegistry):
            raise TypeError("ACTIVE_KNOWLEDGE_REGISTRY_REQUIRED")
        self._schema_majors = self._validate_majors(supported_schema_majors)
        self._configuration_majors = self._validate_majors(supported_configuration_majors)
        self._registry = registry
        self._lock = RLock()
        self._cached_registry_digest = ""
        self._cached_snapshot: KnowledgeRuntimeSnapshot | None = None

    @staticmethod
    def _validate_majors(values: Iterable[int]) -> frozenset[int]:
        try:
            result = frozenset(values)
        except TypeError as exc:
            raise ValueError("INVALID_COMPATIBILITY_CONFIGURATION") from exc
        if not result or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in result):
            raise ValueError("INVALID_COMPATIBILITY_CONFIGURATION")
        return result

    def _compatibility_error(self, entry: ActiveKnowledgeEntry) -> str | None:
        schema, configuration = _major(entry.schema_version), _major(entry.configuration_version)
        if schema not in self._schema_majors:
            return "UNSUPPORTED_KNOWLEDGE_SCHEMA_VERSION"
        if configuration not in self._configuration_majors:
            return "UNSUPPORTED_KNOWLEDGE_CONFIGURATION_VERSION"
        return None

    def _read(self) -> KnowledgeRuntimeSnapshot:
        # Calling list_active is important: it replays the registry and therefore
        # detects corrupt receipts/storage before anything reaches Runtime.
        active = self._registry.list_active()
        registry_body = [entry.to_dict() for entry in active]
        registry_digest = sha256(_canonical(registry_body).encode("utf-8")).hexdigest()
        with self._lock:
            if self._cached_snapshot is not None and self._cached_registry_digest == registry_digest:
                return self._cached_snapshot
            accepted, rejected = [], {}
            for entry in active:
                reason = self._compatibility_error(entry)
                if reason is None:
                    accepted.append(entry)
                else:
                    rejected[entry.knowledge_uuid] = reason
            accepted.sort(key=lambda item: (item.semantic_identity, item.knowledge_uuid))
            body = {"registry_digest": registry_digest, "entries": [item.to_dict() for item in accepted],
                    "rejected": rejected}
            snapshot = KnowledgeRuntimeSnapshot(
                snapshot_digest=sha256(_canonical(body).encode("utf-8")).hexdigest(),
                registry_digest=registry_digest, entries=tuple(accepted), rejected=freeze(rejected))
            self._cached_registry_digest, self._cached_snapshot = registry_digest, snapshot
            return snapshot

    def snapshot(self) -> KnowledgeRuntimeSnapshot:
        """Return the current compatible ACTIVE snapshot; never a stale fallback."""
        return self._read()

    def get_snapshot(self) -> KnowledgeRuntimeSnapshot:
        """Compatibility alias for consumers that use ``get_*`` read APIs."""
        return self.snapshot()

    def list_active(self) -> tuple[ActiveKnowledgeEntry, ...]:
        return self._read().entries

    def get_active(self, knowledge_uuid: str) -> ActiveKnowledgeEntry | None:
        return next((item for item in self._read().entries if item.knowledge_uuid == knowledge_uuid), None)

    def resolve(self, semantic_identity: str) -> ActiveKnowledgeEntry | None:
        return next((item for item in self._read().entries if item.semantic_identity == semantic_identity), None)

    def lookup(self, value: str) -> ActiveKnowledgeEntry | None:
        return self.get_active(value) or self.resolve(value)

