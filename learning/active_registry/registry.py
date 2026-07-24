"""Canonical, read-only exposure of knowledge activated by Promotion Authority."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
from .models import ActiveKnowledgeEntry
from .storage import ActiveRegistryStorage

def _now() -> datetime: return datetime.now(timezone.utc)
def _iso(value: datetime) -> str: return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
def _data(value: Any) -> Mapping[str, Any] | None: return value.to_dict() if hasattr(value, "to_dict") else value if isinstance(value, Mapping) else None

class ActiveKnowledgeRegistry:
    """Append-only projection of successful promotions, never a promotion authority.

    Callers supply already-created promotion artifacts.  This module deliberately
    imports neither promotion, lifecycle, qualification, analytics, nor runtime code.
    """
    def __init__(self, *, root: str | Path = "learning_data", clock=_now) -> None:
        self.storage, self.clock = ActiveRegistryStorage(root), clock

    def _current(self) -> dict[str, ActiveKnowledgeEntry]:
        projected: dict[str, ActiveKnowledgeEntry] = {}
        # Terminal events win same-timestamp replays deterministically.
        terminal_rank = {"ACTIVE": 0, "SUPERSEDED": 1, "RETIRED": 1, "ARCHIVED": 1}
        for entry in sorted(self.storage.all(), key=lambda item: (item.activation_timestamp, terminal_rank[item.status], item.activation_uuid)):
            projected[entry.knowledge_uuid] = entry
        return projected

    @staticmethod
    def _validate_artifacts(promotion_record: Any, promotion_decision: Any) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        record, decision = _data(promotion_record), _data(promotion_decision)
        if not isinstance(record, Mapping): raise ValueError("MISSING_PROMOTION_RECORD")
        if not isinstance(decision, Mapping): raise ValueError("MISSING_PROMOTION_DECISION")
        if record.get("status") != "COMMITTED": raise ValueError("PROMOTION_RECORD_NOT_COMMITTED")
        if decision.get("decision") != "PROMOTE" or decision.get("decision_status") != "APPROVED": raise ValueError("PROMOTION_DECISION_NOT_APPROVED")
        required_record = ("record_uuid", "decision_uuid", "knowledge_uuid", "semantic_identity")
        required_decision = ("decision_uuid", "knowledge_uuid")
        if any(not isinstance(record.get(k), str) or not record[k] for k in required_record): raise ValueError("INVALID_PROMOTION_RECORD")
        if any(not isinstance(decision.get(k), str) or not decision[k] for k in required_decision): raise ValueError("INVALID_PROMOTION_DECISION")
        if record["decision_uuid"] != decision["decision_uuid"] or record["knowledge_uuid"] != decision["knowledge_uuid"]: raise ValueError("BROKEN_PROMOTION_LINEAGE")
        semantic = decision.get("semantic_identity", record["semantic_identity"])
        if semantic != record["semantic_identity"]: raise ValueError("BROKEN_PROMOTION_LINEAGE")
        return record, decision

    def register(self, promotion_record: Any = None, promotion_decision: Any = None, *,
                 activation_reason: str = "promotion", schema_version: str = "1.0",
                 configuration_version: str = "1.0", lineage_reference: str = "",
                 activation_timestamp: str | None = None, supersedes_knowledge_uuid: str = "",
                 status: str = "ACTIVE", metadata: Mapping[str, Any] | None = None) -> ActiveKnowledgeEntry:
        """Append an activation or terminal status event after fail-closed validation."""
        record, decision = self._validate_artifacts(promotion_record, promotion_decision)
        if status not in {"ACTIVE", "RETIRED", "ARCHIVED"}: raise ValueError("INVALID_REGISTRY_TRANSITION")
        timestamp = activation_timestamp or _iso(self.clock())
        lineage = lineage_reference or record["record_uuid"]
        current = self._current()
        knowledge, semantic = record["knowledge_uuid"], record["semantic_identity"]
        old = current.get(supersedes_knowledge_uuid) if supersedes_knowledge_uuid else None
        base = f"{knowledge}:{record['decision_uuid']}:{record['record_uuid']}:{status}:{timestamp}:{supersedes_knowledge_uuid}"
        entry_uuid = str(uuid5(NAMESPACE_URL, base))
        existing_event = next((item for item in self.storage.all() if item.activation_uuid == entry_uuid), None)
        if existing_event:
            return existing_event
        if status == "ACTIVE":
            if knowledge in current and current[knowledge].status == "ACTIVE": raise ValueError("DUPLICATE_ACTIVE_KNOWLEDGE")
            clashes = [entry for entry in current.values() if entry.status == "ACTIVE" and entry.semantic_identity == semantic]
            if clashes and not old: raise ValueError("DUPLICATE_ACTIVE_SEMANTIC_IDENTITY")
            if old:
                if old.status != "ACTIVE" or old.semantic_identity != semantic or old.knowledge_uuid == knowledge: raise ValueError("BROKEN_SUPERSESSION_LINEAGE")
        else:
            existing = current.get(knowledge)
            if not existing or existing.status != "ACTIVE": raise ValueError("BROKEN_RETIREMENT_LINEAGE")
        if old:  # Record the old status first, then expose exactly one replacement ACTIVE record.
            superseded = ActiveKnowledgeEntry(str(uuid5(NAMESPACE_URL, base + ':superseded')), old.knowledge_uuid, old.semantic_identity,
                timestamp, activation_reason, record["decision_uuid"], record["record_uuid"], schema_version, configuration_version,
                lineage, "SUPERSEDED", old.activation_uuid, knowledge, metadata or {})
            self.storage.write(superseded)
        entry = ActiveKnowledgeEntry(entry_uuid, knowledge, semantic, timestamp, activation_reason,
            record["decision_uuid"], record["record_uuid"], schema_version, configuration_version, lineage, status,
            current.get(knowledge).activation_uuid if status != "ACTIVE" and knowledge in current else "", "", metadata or {})
        self.storage.write(entry)
        return entry

    def get_active(self, knowledge_uuid: str) -> ActiveKnowledgeEntry | None:
        entry = self._current().get(knowledge_uuid); return entry if entry and entry.status == "ACTIVE" else None
    def get_by_uuid(self, knowledge_uuid: str) -> ActiveKnowledgeEntry | None: return self._current().get(knowledge_uuid)
    def get_by_semantic_identity(self, semantic_identity: str, *, active_only: bool = True) -> tuple[ActiveKnowledgeEntry, ...]:
        values = [x for x in self._current().values() if x.semantic_identity == semantic_identity and (not active_only or x.status == "ACTIVE")]
        return tuple(sorted(values, key=lambda x: (x.activation_timestamp, x.activation_uuid)))
    def history(self, knowledge_uuid: str | None = None) -> tuple[ActiveKnowledgeEntry, ...]:
        return tuple(x for x in self.storage.all() if knowledge_uuid is None or x.knowledge_uuid == knowledge_uuid)
    def list_active(self) -> tuple[ActiveKnowledgeEntry, ...]:
        return tuple(sorted((x for x in self._current().values() if x.status == "ACTIVE"), key=lambda x: (x.semantic_identity, x.knowledge_uuid)))
    def lookup(self, value: str) -> ActiveKnowledgeEntry | None: return self.get_active(value) or next(iter(self.get_by_semantic_identity(value)), None)
    def resolve(self, semantic_identity: str) -> ActiveKnowledgeEntry | None: return next(iter(self.get_by_semantic_identity(semantic_identity)), None)
