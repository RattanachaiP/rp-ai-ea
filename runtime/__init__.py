"""Runtime-facing Knowledge contracts; no Registry implementation is exported."""

from .knowledge_gateway import (
    ActiveKnowledgeReader,
    KnowledgeRuntimeGateway,
    KnowledgeRuntimeSnapshot,
    RuntimeKnowledgeDescriptor,
)
from .decision_knowledge_interface import (
    DecisionKnowledgeAccessError,
    DecisionKnowledgeInterface,
    DecisionKnowledgeRecord,
    RuntimeQuery,
)

__all__ = [
    "ActiveKnowledgeReader",
    "KnowledgeRuntimeGateway",
    "KnowledgeRuntimeSnapshot",
    "RuntimeKnowledgeDescriptor",
    "DecisionKnowledgeAccessError",
    "DecisionKnowledgeInterface",
    "DecisionKnowledgeRecord",
    "RuntimeQuery",
]
