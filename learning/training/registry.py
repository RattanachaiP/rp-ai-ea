"""Immutable append-only registry for candidate models only."""
from dataclasses import dataclass
from .identity import identity_for
from .models import CandidateModel, TrainingEvidence

@dataclass(frozen=True)
class CandidateRegistryEntry:
    candidate: CandidateModel
    evidence: TrainingEvidence
    sequence: int

    def __post_init__(self):
        if self.evidence.candidate_identity != self.candidate.model_identity: raise ValueError("CANDIDATE_EVIDENCE_MISMATCH")

@dataclass(frozen=True)
class CandidateRegistry:
    entries: tuple[CandidateRegistryEntry, ...] = ()
    previous_registry_identity: str = ""
    registry_identity: str = ""

    def __post_init__(self):
        entries = tuple(self.entries); object.__setattr__(self, "entries", entries)
        if any(e.sequence != i + 1 for i, e in enumerate(entries)): raise ValueError("CANDIDATE_REGISTRY_SEQUENCE_INVALID")
        expected = identity_for("CANDIDATE_REGISTRY", {"previous_registry_identity": self.previous_registry_identity,
            "entries": [(e.candidate.model_identity, e.evidence.evidence_identity, e.sequence) for e in entries]})
        if self.registry_identity and self.registry_identity != expected: raise ValueError("CANDIDATE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)

    def append(self, candidate: CandidateModel, evidence: TrainingEvidence) -> "CandidateRegistry":
        if any(e.candidate.model_identity == candidate.model_identity for e in self.entries): raise ValueError("DUPLICATE_CANDIDATE_MODEL")
        entry = CandidateRegistryEntry(candidate, evidence, len(self.entries) + 1)
        return CandidateRegistry(self.entries + (entry,), self.registry_identity)
