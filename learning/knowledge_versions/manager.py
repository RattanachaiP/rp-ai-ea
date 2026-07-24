"""PR167 authority for immutable Knowledge Version creation and queries.

This boundary deliberately validates and snapshots activation inputs only.  It
never invokes runtime code and never mutates the Active Knowledge Registry.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
from .models import KnowledgeLineage, KnowledgeRollbackDescriptor, KnowledgeVersion, KnowledgeVersionManifest, valid_uuid
from .storage import KnowledgeVersionStorage

def _data(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"): value = value.to_dict()
    elif is_dataclass(value): value = asdict(value)
    if not isinstance(value, Mapping): raise ValueError("INVALID_VERSION_INPUT")
    return json.loads(json.dumps(dict(value), sort_keys=True, default=str, allow_nan=False))

def _canonical(value: Any) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
def _digest(value: Any) -> str: return sha256(_canonical(value).encode()).hexdigest()
def _iso_now() -> str: return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
def _first(data: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] not in (None, ""): return data[name]
    return ""

class KnowledgeVersionManager:
    """Create replay-safe, append-only version snapshots after activation."""
    def __init__(self, *, root="learning_data", architecture_version="PR167", clock=_iso_now):
        if not architecture_version: raise ValueError("INVALID_VERSION_MANAGER_CONFIG")
        self.storage, self.architecture_version, self.clock = KnowledgeVersionStorage(root), architecture_version, clock

    def _compatibility(self, activation, promotion, snapshot) -> dict[str, str]:
        values = {
            "architecture_version": _first(activation, "architecture_version") or _first(promotion, "architecture_version") or self.architecture_version,
            "policy_version": _first(promotion, "policy_version", "governance_version") or _first(activation, "policy_version"),
            "registry_version": _first(snapshot, "registry_version", "schema_version", "version"),
            "runtime_contract": _first(activation, "runtime_contract") or _first(snapshot, "runtime_contract"),
            "knowledge_contract": _first(activation, "knowledge_contract") or _first(promotion, "knowledge_contract"),
            "applicability_contract": _first(activation, "applicability_contract") or _first(promotion, "applicability_contract"),
        }
        if any(not isinstance(v, str) or not v for v in values.values()): raise ValueError("CONTRACT_MISMATCH")
        for key in ("architecture_version", "policy_version", "runtime_contract", "knowledge_contract", "applicability_contract"):
            candidates = {str(x[key]) for x in (activation, promotion, snapshot) if key in x and x[key] not in (None, "")}
            if len(candidates) > 1: raise ValueError("CONTRACT_MISMATCH")
        return values

    def register(self, activation_package: Any, promotion_package: Any, registry_snapshot: Any, *, parent_version_uuid: str = "", rollback_reason="ACTIVATION_ROLLBACK") -> KnowledgeVersion:
        activation, promotion, snapshot = _data(activation_package), _data(promotion_package), _data(registry_snapshot)
        # PR165 PromotionPackage wraps its authoritative decision contract.
        if isinstance(promotion.get("decision"), Mapping):
            promotion = {**promotion, **dict(promotion["decision"])}
        activation_uuid = str(_first(activation, "activation_uuid", "receipt_uuid")); knowledge_uuid = str(_first(activation, "knowledge_uuid"))
        promotion_uuid = str(_first(promotion, "promotion_uuid", "decision_uuid"))
        if not valid_uuid(activation_uuid) or not valid_uuid(knowledge_uuid) or not valid_uuid(promotion_uuid): raise ValueError("INVALID_VERSION_UUID")
        if parent_version_uuid and not valid_uuid(parent_version_uuid): raise ValueError("INVALID_PARENT_VERSION")
        if _first(promotion, "knowledge_uuid") and str(_first(promotion, "knowledge_uuid")) != knowledge_uuid: raise ValueError("CONTRACT_MISMATCH")
        if _first(snapshot, "knowledge_uuid") and str(_first(snapshot, "knowledge_uuid")) != knowledge_uuid: raise ValueError("CONTRACT_MISMATCH")
        compatibility = self._compatibility(activation, promotion, snapshot)
        existing = self.storage.read_all()
        version_uuid = str(uuid5(NAMESPACE_URL, f"knowledge-version:{activation_uuid}:{promotion_uuid}:{_digest(snapshot)}"))
        identical = next((item for item in existing if item.version_uuid == version_uuid), None)
        if identical: return identical
        if any(item.activation_uuid == activation_uuid for item in existing): raise ValueError("DUPLICATE_VERSION")
        parent = next((item for item in existing if item.version_uuid == parent_version_uuid), None) if parent_version_uuid else None
        if parent_version_uuid and parent is None: raise ValueError("INVALID_PARENT_VERSION")
        if parent_version_uuid and parent.knowledge_uuid != knowledge_uuid: raise ValueError("INVALID_PARENT_VERSION")
        if parent_version_uuid and parent.parent_version_uuid == version_uuid: raise ValueError("LINEAGE_CYCLE")
        semantic_version = f"{(int(parent.semantic_version.split('.')[0]) + 1) if parent else 1}.0.0"
        created_at = str(_first(activation, "activated_at", "effective_at", "activation_timestamp", "created_at") or self.clock())
        manifest_source = {"compatibility": compatibility, "activation_package": activation, "promotion_package": promotion, "registry_snapshot": snapshot}
        manifest_digest = _digest(manifest_source)
        metadata = {"manifest_digest": manifest_digest, "promotion_uuid": promotion_uuid, "registry_snapshot_digest": _digest(snapshot)}
        version_source = {"version_uuid": version_uuid, "semantic_version": semantic_version, "created_at": created_at, "knowledge_uuid": knowledge_uuid, "activation_uuid": activation_uuid, "architecture_version": compatibility["architecture_version"], "state": "ACTIVE", "parent_version_uuid": parent_version_uuid, "rollback_parent_uuid": parent_version_uuid, "metadata": metadata}
        version = KnowledgeVersion(version_digest=_digest(version_source), **version_source)
        manifest = KnowledgeVersionManifest(version_uuid, manifest_digest, compatibility, activation, promotion, snapshot)
        lineage = self.lineage_for(version.version_uuid, records=(*existing, version))
        history = {"version_uuid": version.version_uuid, "event": "PUBLISHED", "version_digest": version.version_digest, "manifest_digest": manifest_digest, "created_at": created_at, "parent_version_uuid": parent_version_uuid}
        self.storage.write_version(version); self.storage.write_manifest(manifest); self.storage.write_lineage(lineage); self.storage.write_history(history)
        return version

    create = register
    create_version = register
    def history(self, knowledge_uuid: str | None = None):
        values = self.storage.read_all()
        return tuple(x for x in values if knowledge_uuid is None or x.knowledge_uuid == knowledge_uuid)
    def get(self, version_uuid: str): return next((x for x in self.storage.read_all() if x.version_uuid == version_uuid), None)
    def lineage_for(self, version_uuid: str, *, records=None) -> KnowledgeLineage:
        values = tuple(records or self.storage.read_all()); current = next((x for x in values if x.version_uuid == version_uuid), None)
        if current is None: raise ValueError("UNKNOWN_VERSION")
        branch=[]; cursor=current
        while cursor:
            if cursor.version_uuid in branch: raise ValueError("LINEAGE_CYCLE")
            branch.append(cursor.version_uuid); cursor=next((x for x in values if x.version_uuid == cursor.parent_version_uuid), None) if cursor.parent_version_uuid else None
        return KnowledgeLineage(current.version_uuid, current.parent_version_uuid, tuple(sorted(x.version_uuid for x in values if x.parent_version_uuid == current.version_uuid)), tuple(reversed(branch)))
    def rollback_descriptor(self, version_uuid: str, *, reason="ACTIVATION_ROLLBACK") -> KnowledgeRollbackDescriptor:
        version=self.get(version_uuid)
        if version is None: raise ValueError("UNKNOWN_VERSION")
        parent=self.get(version.rollback_parent_uuid) if version.rollback_parent_uuid else None
        compatible=bool(parent and parent.knowledge_uuid == version.knowledge_uuid and parent.architecture_version == version.architecture_version)
        return KnowledgeRollbackDescriptor(version_uuid, version.rollback_parent_uuid, bool(parent and compatible), reason, compatible)
