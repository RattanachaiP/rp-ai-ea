"""Repository for passive, append-only verified-knowledge governance metadata."""
from __future__ import annotations

from pathlib import Path

from .models import KnowledgeGovernance
from .storage import GovernanceStorage
from .validator import LifecycleValidator


class GovernanceRepository:
    """Persists lifecycle records without reading or mutating runtime knowledge."""

    def __init__(self, root: str | Path = "learning_data") -> None:
        self.storage = GovernanceStorage(root)
        self.validator = LifecycleValidator()

    def save(self, governance: KnowledgeGovernance) -> Path:
        history = self.history(governance.knowledge_uuid)
        if history and history[-1].to_dict() == governance.to_dict():
            return self.storage.path_for(governance.knowledge_uuid, governance.record_version)
        self.validator.validate(governance, history)
        return self.storage.write(governance)

    def history(self, knowledge_uuid: str) -> list[KnowledgeGovernance]:
        return sorted((item for item in self.storage.all() if item.knowledge_uuid == knowledge_uuid), key=lambda item: item.record_version)

    def load(self, knowledge_uuid: str) -> KnowledgeGovernance:
        history = self.history(knowledge_uuid)
        if not history:
            raise FileNotFoundError("GOVERNANCE_NOT_FOUND")
        return history[-1]

    def query(self, *, lifecycle_state: str | None = None, pattern_uuid: str | None = None,
              production_eligible: bool | None = None) -> list[KnowledgeGovernance]:
        current: dict[str, KnowledgeGovernance] = {}
        for item in self.storage.all():
            if item.knowledge_uuid not in current or item.record_version > current[item.knowledge_uuid].record_version:
                current[item.knowledge_uuid] = item
        result = list(current.values())
        if lifecycle_state is not None:
            result = [item for item in result if item.current_lifecycle_state == lifecycle_state]
        if pattern_uuid is not None:
            result = [item for item in result if item.pattern_uuid == pattern_uuid]
        if production_eligible is not None:
            result = [item for item in result if item.production_eligible is production_eligible]
        return sorted(result, key=lambda item: (item.pattern_uuid, item.knowledge_uuid))
