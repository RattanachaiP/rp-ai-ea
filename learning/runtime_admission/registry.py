"""Append-only, compare-and-swap Runtime Admission evidence registry."""
from dataclasses import dataclass

from learning.deployment.contracts import _revalidate
from learning.promotion.identity import identity_for
from .contracts import AdmissionRegistryEntry, RuntimeAdmissionEvidence


@dataclass(frozen=True)
class RuntimeAdmissionRegistry:
    entries: tuple[AdmissionRegistryEntry, ...] = ()
    rejections: tuple[RuntimeAdmissionEvidence, ...] = ()
    previous_registry_identity: str | None = None
    registry_identity: str = ""
    def __post_init__(self):
        entries, rejections = tuple(self.entries), tuple(self.rejections)
        for value in entries + rejections: _revalidate(value)
        for index, entry in enumerate(entries):
            if (entry.sequence != index + 1 or entry.previous_entry_identity !=
                    (None if index == 0 else entries[index - 1].entry_identity)):
                raise ValueError("ADMISSION_REGISTRY_LINEAGE_INVALID")
        handoffs = [x.admission.handoff_identity for x in entries]
        runtimes = [x.admission.runtime_instance_identity for x in entries]
        if len(handoffs) != len(set(handoffs)) or len(runtimes) != len(set(runtimes)):
            raise ValueError("RUNTIME_ADMISSION_REPLAY")
        predecessors = set()
        if entries: predecessors.add(self._identity(entries[:-1], rejections))
        if rejections: predecessors.add(self._identity(entries, rejections[:-1]))
        if predecessors:
            if self.previous_registry_identity not in predecessors:
                raise ValueError("ADMISSION_REGISTRY_PREDECESSOR_INVALID")
        elif self.previous_registry_identity is not None:
            raise ValueError("ADMISSION_REGISTRY_PREDECESSOR_INVALID")
        expected = self._identity(entries, rejections)
        if self.registry_identity and self.registry_identity != expected:
            raise ValueError("ADMISSION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "rejections", rejections)
        object.__setattr__(self, "registry_identity", expected)

    @staticmethod
    def _identity(entries, rejections):
        return identity_for("PR278_ADMISSION_REGISTRY", {
            "entries": tuple(x.entry_identity for x in entries),
            "rejections": tuple(x.evidence_identity for x in rejections),
        })

    def contains(self, handoff_identity, runtime_instance_identity):
        return any(x.admission.handoff_identity == handoff_identity or
                   x.admission.runtime_instance_identity == runtime_instance_identity
                   for x in self.entries)

    def append(self, entry, expected):
        if expected != self.registry_identity: raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(entry)
        if self.contains(entry.admission.handoff_identity, entry.admission.runtime_instance_identity):
            raise ValueError("RUNTIME_ADMISSION_REPLAY")
        return RuntimeAdmissionRegistry(self.entries + (entry,), self.rejections,
                                        self.registry_identity)

    def reject(self, evidence, expected):
        if expected != self.registry_identity: raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(evidence)
        if evidence.accepted: raise ValueError("ADMISSION_REJECTION_INVALID")
        return RuntimeAdmissionRegistry(self.entries, self.rejections + (evidence,),
                                        self.registry_identity)
