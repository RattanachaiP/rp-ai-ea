"""Runtime-facing contracts that do not perform publication or execution."""

from .knowledge_gateway import KnowledgeRuntimeGateway, KnowledgeRuntimeSnapshot

__all__ = ["KnowledgeRuntimeGateway", "KnowledgeRuntimeSnapshot"]
