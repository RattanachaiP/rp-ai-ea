"""Append-only, compare-and-swap Runtime Admission evidence registry."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate
from learning.promotion.identity import identity_for
from .contracts import (AdmissionAuthorizationRevocation, AdmissionRegistryEntry,
    RuntimeAdmissionEvidence)

@dataclass(frozen=True)
class RuntimeAdmissionRegistry:
    entries:tuple[AdmissionRegistryEntry,...]=(); rejections:tuple[RuntimeAdmissionEvidence,...]=()
    previous_registry_identity:str|None=None; registry_identity:str=""
    revocations:tuple[AdmissionAuthorizationRevocation,...]=()
    def __post_init__(self):
        entries,rejections,revocations=tuple(self.entries),tuple(self.rejections),tuple(self.revocations)
        for value in entries+rejections+revocations:_revalidate(value)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("ADMISSION_REGISTRY_LINEAGE_INVALID")
        handoffs=[x.admission_authorization.handoff_identity for x in entries]
        generations=[(x.admission_authorization.runtime_instance_identity,x.admission_authorization.activation_generation) for x in entries]
        if len(handoffs)!=len(set(handoffs)) or len(generations)!=len(set(generations)): raise ValueError("RUNTIME_ADMISSION_REPLAY")
        predecessors=set()
        if entries:predecessors.add(self._identity(entries[:-1],rejections,revocations))
        if rejections:predecessors.add(self._identity(entries,rejections[:-1],revocations))
        if revocations:predecessors.add(self._identity(entries,rejections,revocations[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None): raise ValueError("ADMISSION_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,rejections,revocations)
        if self.registry_identity and self.registry_identity!=expected:raise ValueError("ADMISSION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries);object.__setattr__(self,"rejections",rejections);object.__setattr__(self,"revocations",revocations);object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,rejections,revocations):return identity_for("PR278_ADMISSION_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"rejections":tuple(x.evidence_identity for x in rejections),"revocations":tuple(x.revocation_identity for x in revocations)})
    def contains(self,handoff_identity,runtime_instance_identity,activation_generation):
        return any(x.admission_authorization.handoff_identity==handoff_identity or
            (x.admission_authorization.runtime_instance_identity,x.admission_authorization.activation_generation)==(runtime_instance_identity,activation_generation) for x in self.entries)
    def append(self,entry,expected):
        if expected!=self.registry_identity:raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(entry);a=entry.admission_authorization
        if self.contains(a.handoff_identity,a.runtime_instance_identity,a.activation_generation):raise ValueError("RUNTIME_ADMISSION_REPLAY")
        return RuntimeAdmissionRegistry(self.entries+(entry,),self.rejections,self.registry_identity,"",self.revocations)
    def reject(self,evidence,expected):
        if expected!=self.registry_identity:raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(evidence)
        if evidence.accepted:raise ValueError("ADMISSION_REJECTION_INVALID")
        return RuntimeAdmissionRegistry(self.entries,self.rejections+(evidence,),self.registry_identity,"",self.revocations)
    def revoke(self,revocation,expected):
        if expected!=self.registry_identity:raise ValueError("ADMISSION_REGISTRY_CONFLICT")
        _revalidate(revocation)
        if not any(x.admission_authorization.authorization_identity==revocation.admission_authorization_identity for x in self.entries):
            raise ValueError("ADMISSION_REVOCATION_TARGET_UNKNOWN")
        if any(x.admission_authorization_identity==revocation.admission_authorization_identity for x in self.revocations):
            raise ValueError("ADMISSION_REVOCATION_REPLAY")
        return RuntimeAdmissionRegistry(self.entries,self.rejections,self.registry_identity,"",self.revocations+(revocation,))
    def is_revoked(self,authorization_identity,at):
        from learning.deployment.contracts import _utc
        return any(x.admission_authorization_identity==authorization_identity and
            _utc(x.revoked_at)<=_utc(at) for x in self.revocations)
