"""Append-only, compare-and-swap Runtime Admission evidence registry."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate
from learning.promotion.identity import identity_for
from .contracts import AdmissionRegistryEntry, RuntimeAdmissionEvidence

@dataclass(frozen=True)
class RuntimeAdmissionRegistry:
    entries:tuple[AdmissionRegistryEntry,...]=(); rejections:tuple[RuntimeAdmissionEvidence,...]=()
    previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries,rejections=tuple(self.entries),tuple(self.rejections)
        for value in entries+rejections:_revalidate(value)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("ADMISSION_REGISTRY_LINEAGE_INVALID")
        handoffs=[x.admission_authorization.handoff_identity for x in entries]
        generations=[(x.admission_authorization.runtime_instance_identity,x.admission_authorization.activation_generation) for x in entries]
        if len(handoffs)!=len(set(handoffs)) or len(generations)!=len(set(generations)): raise ValueError("RUNTIME_ADMISSION_REPLAY")
        predecessors=set()
        if entries:predecessors.add(self._identity(entries[:-1],rejections))
        if rejections:predecessors.add(self._identity(entries,rejections[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None): raise ValueError("ADMISSION_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,rejections)
        if self.registry_identity and self.registry_identity!=expected:raise ValueError("ADMISSION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries);object.__setattr__(self,"rejections",rejections);object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,rejections):return identity_for("PR278_ADMISSION_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"rejections":tuple(x.evidence_identity for x in rejections)})
    def contains(self,handoff_identity,runtime_instance_identity,activation_generation):
        return any(x.admission_authorization.handoff_identity==handoff_identity or
            (x.admission_authorization.runtime_instance_identity,x.admission_authorization.activation_generation)==(runtime_instance_identity,activation_generation) for x in self.entries)
    def append(self,entry,expected):
        if expected!=self.registry_identity:raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(entry);a=entry.admission_authorization
        if self.contains(a.handoff_identity,a.runtime_instance_identity,a.activation_generation):raise ValueError("RUNTIME_ADMISSION_REPLAY")
        return RuntimeAdmissionRegistry(self.entries+(entry,),self.rejections,self.registry_identity)
    def reject(self,evidence,expected):
        if expected!=self.registry_identity:raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(evidence)
        if evidence.accepted:raise ValueError("ADMISSION_REJECTION_INVALID")
        return RuntimeAdmissionRegistry(self.entries,self.rejections+(evidence,),self.registry_identity)
