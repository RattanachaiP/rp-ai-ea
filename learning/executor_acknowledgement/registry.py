"""Append-only, compare-and-swap PR279 acknowledgement registry."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate
from learning.promotion.identity import identity_for
from .contracts import ExecutorAcknowledgementRegistryEntry, ExecutorReadinessEvidence

@dataclass(frozen=True)
class ExecutorAcknowledgementRegistry:
    entries:tuple[ExecutorAcknowledgementRegistryEntry,...]=()
    rejections:tuple[ExecutorReadinessEvidence,...]=()
    previous_registry_identity:str|None=None
    registry_identity:str=""
    def __post_init__(self):
        entries,rejections=tuple(self.entries),tuple(self.rejections)
        for value in entries+rejections:_revalidate(value)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity):
                raise ValueError("ACKNOWLEDGEMENT_REGISTRY_LINEAGE_INVALID")
        attestations=[x.acknowledgement.attestation_identity for x in entries]
        nonce_sessions=[(x.acknowledgement.executor_instance_identity,
            x.acknowledgement.executor_session_identity,
            x.acknowledgement_evidence.attestation_nonce) for x in entries]
        authorizations=[x.acknowledgement.executor_admission_authorization_identity for x in entries]
        if (len(attestations)!=len(set(attestations)) or len(nonce_sessions)!=len(set(nonce_sessions))
                or len(authorizations)!=len(set(authorizations))):
            raise ValueError("EXECUTOR_ATTESTATION_REPLAY")
        predecessors=set()
        if entries:predecessors.add(self._identity(entries[:-1],rejections))
        if rejections:predecessors.add(self._identity(entries,rejections[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None):
            raise ValueError("ACKNOWLEDGEMENT_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,rejections)
        if self.registry_identity and self.registry_identity!=expected:raise ValueError("ACKNOWLEDGEMENT_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries);object.__setattr__(self,"rejections",rejections);object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,rejections):return identity_for("PR279_ACKNOWLEDGEMENT_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"rejections":tuple(x.evidence_identity for x in rejections)})
    def contains_attestation(self,attestation_identity):
        return any(x.acknowledgement.attestation_identity==attestation_identity for x in self.entries)
    def contains_nonce_session(self,nonce,instance,session):
        # The evidence retains the nonce and the entry retains its exact executor instance/session.
        return any(getattr(x.acknowledgement_evidence,"attestation_nonce",None)==nonce and
            x.acknowledgement.executor_instance_identity==instance and
            x.acknowledgement.executor_session_identity==session for x in self.entries)
    def contains_authorization(self,authorization_identity):
        return any(x.acknowledgement.executor_admission_authorization_identity==authorization_identity for x in self.entries)
    def append(self,entry,expected):
        if expected!=self.registry_identity:raise ValueError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
        _revalidate(entry);a=entry.acknowledgement
        if self.contains_attestation(a.attestation_identity) or self.contains_authorization(a.executor_admission_authorization_identity):
            raise ValueError("EXECUTOR_ATTESTATION_REPLAY")
        return ExecutorAcknowledgementRegistry(self.entries+(entry,),self.rejections,self.registry_identity)
    def reject(self,evidence,expected):
        if expected!=self.registry_identity:raise ValueError("ACKNOWLEDGEMENT_REGISTRY_CONFLICT")
        _revalidate(evidence)
        if evidence.accepted:raise ValueError("ACKNOWLEDGEMENT_REJECTION_INVALID")
        return ExecutorAcknowledgementRegistry(self.entries,self.rejections+(evidence,),self.registry_identity)
