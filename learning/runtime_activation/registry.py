"""Append-only activation registry with optimistic concurrency lineage."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate, _utc
from learning.promotion.identity import identity_for
from learning.release import ActivationRevocation, ReleaseRegistry
from .contracts import ActivationEvidence, ActivationRegistryEntry

@dataclass(frozen=True)
class ActivationRegistry:
    entries:tuple[ActivationRegistryEntry,...]=(); rejections:tuple[ActivationEvidence,...]=()
    revocations:tuple[ActivationRevocation,...]=(); previous_registry_identity:str|None=None
    registry_identity:str=""
    def __post_init__(self):
        entries,rejections,revocations=map(tuple,(self.entries,self.rejections,self.revocations))
        for collection in (entries,rejections,revocations):
            for x in collection:_revalidate(x)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("ACTIVATION_REGISTRY_LINEAGE_INVALID")
        ids=[e.consumed_authorization.authorization.authorization_identity for e in entries]
        if len(ids)!=len(set(ids)): raise ValueError("ACTIVATION_REPLAY")
        predecessors=set()
        if entries: predecessors.add(self._identity(entries[:-1],rejections,revocations))
        if rejections: predecessors.add(self._identity(entries,rejections[:-1],revocations))
        if revocations: predecessors.add(self._identity(entries,rejections,revocations[:-1]))
        if self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None: raise ValueError("ACTIVATION_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,rejections,revocations)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("ACTIVATION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries);object.__setattr__(self,"rejections",rejections);object.__setattr__(self,"revocations",revocations);object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,rejections,revocations): return identity_for("PR277_ACTIVATION_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"rejections":tuple(x.evidence_identity for x in rejections),"revocations":tuple(x.revocation_identity for x in revocations)})
    def is_consumed(self,x): return any(e.consumed_authorization.authorization.authorization_identity==x for e in self.entries)
    def is_revoked(self,x,at): return any(r.authorization_identity==x and _utc(r.issued_at)<=_utc(at) for r in self.revocations)
    def _cas(self,expected):
        if expected!=self.registry_identity: raise ValueError("ACTIVATION_REGISTRY_CONFLICT")
    def append(self,entry,expected_registry_identity):
        self._cas(expected_registry_identity);_revalidate(entry)
        if self.is_consumed(entry.consumed_authorization.authorization.authorization_identity): raise ValueError("ACTIVATION_REPLAY")
        return ActivationRegistry(self.entries+(entry,),self.rejections,self.revocations,self.registry_identity)
    def reject(self,evidence,expected_registry_identity):
        self._cas(expected_registry_identity);_revalidate(evidence)
        if evidence.accepted: raise ValueError("REJECTION_EVIDENCE_INVALID")
        return ActivationRegistry(self.entries,self.rejections+(evidence,),self.revocations,self.registry_identity)
    def revoke(self,record,release_registry:ReleaseRegistry,expected_registry_identity):
        self._cas(expected_registry_identity);_revalidate(record);_revalidate(release_registry)
        known=any(e.decision.runtime_activation_authorization.authorization_identity==record.authorization_identity for e in release_registry.entries)
        if not known: raise ValueError("ACTIVATION_REVOCATION_UNKNOWN")
        if any(x.authorization_identity==record.authorization_identity for x in self.revocations): raise ValueError("ACTIVATION_REVOCATION_REPLAY")
        return ActivationRegistry(self.entries,self.rejections,self.revocations+(record,),self.registry_identity)
