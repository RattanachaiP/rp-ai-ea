"""Runtime-facing Knowledge contracts; no Registry implementation is exported."""

from .knowledge_gateway import (
    ActiveKnowledgeReader,
    KnowledgeRuntimeGateway,
    KnowledgeRuntimeSnapshot,
    RuntimeKnowledgeDescriptor,
)
from .knowledge_applicability import APPLICABILITY_REPORT_CONTRACT_VERSION
from .decision_knowledge_interface import (
    DecisionKnowledgeAccessError,
    DecisionKnowledgeInterface,
    DecisionKnowledgeRecord,
    DecisionKnowledgeSnapshot,
)
from .decision_knowledge_observation import (
    DecisionKnowledgeObservationError,
    DecisionKnowledgeObservationRecord,
    DecisionKnowledgeObservationRepository,
    DecisionKnowledgeObserver,
    KnowledgeObservation,
    ObservedKnowledgeReference,
)

__all__ = [
    "ActiveKnowledgeReader",
    "KnowledgeRuntimeGateway",
    "KnowledgeRuntimeSnapshot",
    "RuntimeKnowledgeDescriptor",
    "APPLICABILITY_REPORT_CONTRACT_VERSION",
    "DecisionKnowledgeAccessError",
    "DecisionKnowledgeInterface",
    "DecisionKnowledgeRecord",
    "DecisionKnowledgeSnapshot",
    "DecisionKnowledgeObservationError",
    "DecisionKnowledgeObservationRecord",
    "DecisionKnowledgeObservationRepository",
    "DecisionKnowledgeObserver",
    "KnowledgeObservation",
    "ObservedKnowledgeReference",
]
