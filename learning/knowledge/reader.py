"""Read facade for trusted knowledge consumers."""
from __future__ import annotations
from .knowledge import Knowledge
from .repository import KnowledgeRepository

class KnowledgeReader:
    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self.repository = repository or KnowledgeRepository()
    def load(self, knowledge_uuid: str) -> Knowledge: return self.repository.load(knowledge_uuid)
    def query(self, **filters: object) -> list[Knowledge]: return self.repository.query(**filters)  # type: ignore[arg-type]
    def latest(self, pattern_uuid: str) -> Knowledge | None: return self.repository.latest(pattern_uuid)
    def history(self, pattern_uuid: str) -> list[Knowledge]: return self.repository.history(pattern_uuid)
