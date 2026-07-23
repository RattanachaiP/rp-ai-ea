"""Authoritative repository for statistically verified trading knowledge only."""
from .builder import KnowledgeBuilder
from .knowledge import Knowledge
from .reader import KnowledgeReader
from .registry import KnowledgeRegistry
from .repository import KnowledgeRepository
from .validator import KnowledgeValidationError, KnowledgeValidator
from .writer import KnowledgeWriter

def build(verified_pattern: object, *, repository: KnowledgeRepository | None = None, **options: object) -> Knowledge:
    return (repository or KnowledgeRepository()).build(verified_pattern, **options)
def load(knowledge_uuid: str, *, repository: KnowledgeRepository | None = None) -> Knowledge:
    return (repository or KnowledgeRepository()).load(knowledge_uuid)
def query(*, repository: KnowledgeRepository | None = None, **filters: object) -> list[Knowledge]:
    return (repository or KnowledgeRepository()).query(**filters)  # type: ignore[arg-type]
def latest(pattern_uuid: str, *, repository: KnowledgeRepository | None = None) -> Knowledge | None:
    return (repository or KnowledgeRepository()).latest(pattern_uuid)
def history(pattern_uuid: str, *, repository: KnowledgeRepository | None = None) -> list[Knowledge]:
    return (repository or KnowledgeRepository()).history(pattern_uuid)
__all__ = ["Knowledge", "KnowledgeBuilder", "KnowledgeReader", "KnowledgeRegistry", "KnowledgeRepository", "KnowledgeValidationError", "KnowledgeValidator", "KnowledgeWriter", "build", "load", "query", "latest", "history"]
