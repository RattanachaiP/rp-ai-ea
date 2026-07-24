"""Runtime-facing Knowledge contracts; no Registry implementation is exported."""

from .knowledge_gateway import (
    ActiveKnowledgeReader,
    KnowledgeRuntimeGateway,
    KnowledgeRuntimeSnapshot,
    RuntimeKnowledgeDescriptor,
)

__all__ = [
    "ActiveKnowledgeReader",
    "KnowledgeRuntimeGateway",
    "KnowledgeRuntimeSnapshot",
    "RuntimeKnowledgeDescriptor",
]
