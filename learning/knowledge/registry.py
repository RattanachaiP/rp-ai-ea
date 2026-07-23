"""Read-only knowledge schema and status registry."""
from .schema import KNOWLEDGE_STATUSES, KNOWLEDGE_VERSION, SCHEMA_VERSION
class KnowledgeRegistry:
    knowledge_version = KNOWLEDGE_VERSION
    schema_version = SCHEMA_VERSION
    statuses = tuple(sorted(KNOWLEDGE_STATUSES))
