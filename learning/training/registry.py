from dataclasses import dataclass
from .identity import identity_for
from .models import CandidateModel, TrainingEvidence
@dataclass(frozen=True)
class CandidateRegistryEntry:
    candidate: CandidateModel; evidence: TrainingEvidence; sequence: int; previous_entry_identity: str | None; entry_identity: str = ""
    def __post_init__(self):
        CandidateModel(**self.candidate.__dict__); TrainingEvidence(**self.evidence.__dict__)
        if (type(self.sequence) is not int or self.sequence < 1 or (self.sequence == 1) != (self.previous_entry_identity is None)
                or self.evidence.candidate_identity != self.candidate.model_identity
                or self.evidence.lineage_identity != self.candidate.lineage.lineage_identity
                or self.evidence.configuration_identity != self.candidate.lineage.configuration_identity
                or self.evidence.policy_identity != self.candidate.lineage.policy_identity):
            raise ValueError("CANDIDATE_REGISTRY_ENTRY_BINDING_INVALID")
        expected = identity_for("CANDIDATE_REGISTRY_ENTRY", self.canonical_payload())
        if self.entry_identity and self.entry_identity != expected: raise ValueError("CANDIDATE_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)
    def canonical_payload(self): return {"candidate_identity": self.candidate.model_identity, "evidence_identity": self.evidence.evidence_identity,
        "lineage_identity": self.candidate.lineage.lineage_identity, "policy_identity": self.evidence.policy_identity,
        "sequence": self.sequence, "previous_entry_identity": self.previous_entry_identity}
@dataclass(frozen=True)
class CandidateRegistry:
    entries: tuple[CandidateRegistryEntry, ...] = (); previous_registry_identity: str | None = None; registry_identity: str = ""
    def __post_init__(self):
        entries = tuple(self.entries); object.__setattr__(self, "entries", entries)
        for i, entry in enumerate(entries):
            CandidateRegistryEntry(**entry.__dict__)
            expected_previous = None if i == 0 else entries[i-1].entry_identity
            if entry.sequence != i + 1 or entry.previous_entry_identity != expected_previous: raise ValueError("CANDIDATE_REGISTRY_ANCESTRY_INVALID")
        expected_predecessor = None if not entries else self._prefix_identity(entries[:-1])
        if self.previous_registry_identity != expected_predecessor: raise ValueError("CANDIDATE_REGISTRY_PREDECESSOR_INVALID")
        if len({e.candidate.model_identity for e in entries}) != len(entries): raise ValueError("DUPLICATE_CANDIDATE_MODEL")
        expected = self._prefix_identity(entries)
        if self.registry_identity and self.registry_identity != expected: raise ValueError("CANDIDATE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)
    @staticmethod
    def _prefix_identity(entries):
        previous = None if len(entries) < 2 else CandidateRegistry._prefix_identity(entries[:-1])
        return identity_for("CANDIDATE_REGISTRY", {"previous_registry_identity": previous, "entry_identities": tuple(e.entry_identity for e in entries)})
    def append(self, candidate, evidence):
        if any(e.candidate.model_identity == candidate.model_identity for e in self.entries): raise ValueError("DUPLICATE_CANDIDATE_MODEL")
        entry = CandidateRegistryEntry(candidate, evidence, len(self.entries)+1, None if not self.entries else self.entries[-1].entry_identity)
        return CandidateRegistry(self.entries+(entry,), self.registry_identity)
