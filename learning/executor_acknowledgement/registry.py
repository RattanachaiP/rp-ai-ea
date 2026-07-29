"""Append-only, compare-and-swap PR279 acknowledgement registry."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate, _utc
from learning.promotion.identity import identity_for
from .contracts import (AdmissionAuthorizationRevocation,
    ExecutorAcknowledgementRegistryEntry, ExecutorReadinessEvidence)

@dataclass(frozen=True)
class ExecutorAcknowledgementRegistry:
    entries: tuple[ExecutorAcknowledgementRegistryEntry,...]=()
    rejections: tuple[ExecutorReadinessEvidence,...]=()
    revocations: tuple[AdmissionAuthorizationRevocation,...]=()
    previous_registry_identity: str|None=None; registry_identity: str=""
    def __post_init__(self):
        entries,rejections,revocations=tuple(self.entries),tuple(self.rejections),tuple(self.revocations)
        for value in entries+rejections+revocations: _revalidate(value)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("ACKNOWLEDGEMENT_REGISTRY_LINEAGE_INVALID")
        admissions=[x.acknowledgement.admission_authorization_identity for x in entries]
        generations=[(x.acknowledgement.runtime_instance_identity,x.acknowledgement.activation_generation) for x in entries]
        if len(admissions)!=len(set(admissions)) or len(generations)!=len(set(generations)): raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_REPLAY")
        if len({x.revocation_identity for x in revocations})!=len(revocations): raise ValueError("ACKNOWLEDGEMENT_REVOCATION_REPLAY")
        predecessors=set()
        if entries: predecessors.add(self._identity(entries[:-1],rejections,revocations))
        if rejections: predecessors.add(self._identity(entries,rejections[:-1],revocations))
        if revocations: predecessors.add(self._identity(entries,rejections,revocations[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None): raise ValueError("ACKNOWLEDGEMENT_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,rejections,revocations)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries);object.__setattr__(self,"rejections",rejections);object.__setattr__(self,"revocations",revocations);object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,rejections,revocations): return identity_for("PR279_ACKNOWLEDGEMENT_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"rejections":tuple(x.evidence_identity for x in rejections),"revocations":tuple(x.revocation_identity for x in revocations)})
    def contains(self,authorization_identity,runtime_identity,generation):
        return any(x.acknowledgement.admission_authorization_identity==authorization_identity or (x.acknowledgement.runtime_instance_identity,x.acknowledgement.activation_generation)==(runtime_identity,generation) for x in self.entries)
    def is_revoked(self,authorization_identity,at):
        moment=_utc(at); return any(x.admission_authorization_identity==authorization_identity and _utc(x.revoked_at)<=moment for x in self.revocations)
    def append(self,entry,expected):
        if expected!=self.registry_identity: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
        _revalidate(entry); a=entry.acknowledgement
        if self.contains(a.admission_authorization_identity,a.runtime_instance_identity,a.activation_generation): raise ValueError("EXECUTOR_ACKNOWLEDGEMENT_REPLAY")
        return ExecutorAcknowledgementRegistry(self.entries+(entry,),self.rejections,self.revocations,self.registry_identity)
    def reject(self,evidence,expected):
        if expected!=self.registry_identity: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
        _revalidate(evidence)
        if evidence.accepted: raise ValueError("ACKNOWLEDGEMENT_REJECTION_INVALID")
        return ExecutorAcknowledgementRegistry(self.entries,self.rejections+(evidence,),self.revocations,self.registry_identity)
    def revoke(self,revocation,expected):
        if expected!=self.registry_identity: raise ValueError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
        _revalidate(revocation)
        if any(x.admission_authorization_identity==revocation.admission_authorization_identity for x in self.revocations): raise ValueError("ACKNOWLEDGEMENT_REVOCATION_REPLAY")
        return ExecutorAcknowledgementRegistry(self.entries,self.rejections,self.revocations+(revocation,),self.registry_identity)
