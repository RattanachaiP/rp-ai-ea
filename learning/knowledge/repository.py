"""Authoritative append-only repository for trusted trading knowledge."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .builder import KnowledgeBuilder
from .knowledge import Knowledge
from .storage import KnowledgeStorage
from .validator import KnowledgeValidator


class KnowledgeRepository:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.storage = KnowledgeStorage(root)
        self.validator = KnowledgeValidator()
        self.builder = KnowledgeBuilder()

    def build(self, verified_pattern: Mapping[str, Any] | Any, **options: Any) -> Knowledge:
        """Build, validate, and append a new knowledge version from a VERIFIED pattern."""
        knowledge = self.builder.build(verified_pattern, existing=self.storage.all(), **options)
        self.save(knowledge)
        return knowledge

    def save(self, knowledge: Knowledge) -> Path:
        existing = self.storage.all()
        for prior in existing:
            if prior.knowledge_uuid == knowledge.knowledge_uuid:
                if prior.to_dict() == knowledge.to_dict():
                    return self.storage.path_for(knowledge.knowledge_uuid)
                raise FileExistsError("KNOWLEDGE_IMMUTABLE")
        self.validator.validate(knowledge, existing)
        return self.storage.write(knowledge)

    def load(self, knowledge_uuid: str) -> Knowledge:
        return self.storage.read(knowledge_uuid)

    def query(self, *, pattern_uuid: str | None = None, validation_uuid: str | None = None,
              knowledge_status: str | None = None, status: str | None = None, symbol: str | None = None,
              session: str | None = None, market_state: str | None = None) -> list[Knowledge]:
        result = self.storage.all()
        if pattern_uuid is not None:
            result = [item for item in result if item.pattern_uuid == pattern_uuid]
        if validation_uuid is not None:
            result = [item for item in result if item.validation_uuid == validation_uuid]
        if knowledge_status is not None and status is not None and knowledge_status != status:
            raise ValueError("CONFLICTING_STATUS_FILTERS")
        requested_status = knowledge_status if knowledge_status is not None else status
        if requested_status is not None:
            result = [item for item in result if item.knowledge_status == requested_status]
        if symbol is not None:
            result = [item for item in result if symbol in item.applicable_symbols]
        if session is not None:
            result = [item for item in result if session in item.applicable_sessions]
        if market_state is not None:
            result = [item for item in result if market_state in item.applicable_market_states]
        return sorted(result, key=lambda item: (item.pattern_uuid, item.knowledge_version, item.created_timestamp))

    def history(self, pattern_uuid: str) -> list[Knowledge]:
        return sorted(self.query(pattern_uuid=pattern_uuid), key=lambda item: item.knowledge_version)

    def latest(self, pattern_uuid: str) -> Knowledge | None:
        versions = self.history(pattern_uuid)
        return versions[-1] if versions else None
