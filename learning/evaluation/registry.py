"""Ordered append-only evaluation registry with complete ancestry."""
from dataclasses import dataclass
from .identity import identity_for
from .models import EvaluationReport

@dataclass(frozen=True)
class EvaluationRegistryEntry:
    report: EvaluationReport; sequence: int; previous_entry_identity: str | None; entry_identity: str = ""
    def __post_init__(self):
        EvaluationReport(**self.report.__dict__)
        if type(self.sequence) is not int or self.sequence < 1 or (self.sequence == 1) != (self.previous_entry_identity is None):
            raise ValueError("EVALUATION_REGISTRY_ENTRY_INVALID")
        expected = identity_for("EVALUATION_REGISTRY_ENTRY", self.canonical_payload())
        if self.entry_identity and self.entry_identity != expected: raise ValueError("EVALUATION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entry_identity", expected)
    def canonical_payload(self): return {"report_identity": self.report.report_identity, "candidate_identity": self.report.candidate_identity,
        "evaluation_dataset_identity": self.report.evaluation_dataset_identity, "policy_identity": self.report.policy.policy_identity,
        "sequence": self.sequence, "previous_entry_identity": self.previous_entry_identity}

@dataclass(frozen=True)
class EvaluationRegistry:
    entries: tuple[EvaluationRegistryEntry, ...] = (); previous_registry_identity: str | None = None; registry_identity: str = ""
    def __post_init__(self):
        entries = tuple(self.entries); object.__setattr__(self, "entries", entries)
        for index, entry in enumerate(entries):
            EvaluationRegistryEntry(**entry.__dict__)
            if entry.sequence != index+1 or entry.previous_entry_identity != (None if index == 0 else entries[index-1].entry_identity):
                raise ValueError("EVALUATION_REGISTRY_ANCESTRY_INVALID")
        keys = tuple((x.report.candidate_identity, x.report.evaluation_dataset_identity, x.report.policy.policy_identity) for x in entries)
        if len(set(keys)) != len(keys): raise ValueError("DUPLICATE_CANDIDATE_EVALUATION")
        predecessor = None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity != predecessor: raise ValueError("EVALUATION_REGISTRY_PREDECESSOR_INVALID")
        expected = self._identity(entries)
        if self.registry_identity and self.registry_identity != expected: raise ValueError("EVALUATION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)
    @staticmethod
    def _identity(entries):
        previous = None if len(entries) < 2 else EvaluationRegistry._identity(entries[:-1])
        return identity_for("EVALUATION_REGISTRY", {"previous_registry_identity": previous,
            "entry_identities": tuple(x.entry_identity for x in entries)})
    def append(self, report):
        entry = EvaluationRegistryEntry(report, len(self.entries)+1, None if not self.entries else self.entries[-1].entry_identity)
        return EvaluationRegistry(self.entries+(entry,), self.registry_identity)
