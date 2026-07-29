"""Immutable append-only CAS registry: the sole PR280 status source of truth."""
from dataclasses import dataclass

from learning.deployment.contracts import _revalidate, _utc
from learning.promotion.identity import identity_for
from .contracts import (RuntimeStartupAuthorizationConsumption, RuntimeStartupRegistryEntry,
    StartupGovernanceStatus, STARTUP_AUTHORIZED, STARTUP_REJECTED)

SUBJECT_ATTRIBUTE = {
    "ACKNOWLEDGEMENT_AUTHORIZATION":"executor_acknowledgement_authorization_identity",
    "ACKNOWLEDGEMENT_ENTRY":"acknowledgement_registry_entry_identity",
    "STARTUP_AUTHORIZATION":"authorization_identity", "ARTIFACT":"artifact_identity",
    "RUNTIME_CONTRACT":"runtime_contract_identity", "RUNTIME_INSTANCE":"runtime_instance_identity",
    "ACTIVATION_GENERATION":"activation_generation"}

def status_applies(status, subject, at):
    if _utc(status.effective_at) > _utc(at): return False
    if status.subject_type == "GLOBAL": return True
    value=getattr(subject, SUBJECT_ATTRIBUTE[status.subject_type], None)
    return str(value) == status.subject_identity

@dataclass(frozen=True)
class RuntimeStartupRegistry:
    entries: tuple[RuntimeStartupRegistryEntry,...] = ()
    consumptions: tuple[RuntimeStartupAuthorizationConsumption,...] = ()
    governance_statuses: tuple[StartupGovernanceStatus,...] = ()
    previous_registry_identity: str|None = None
    registry_identity: str = ""
    def __post_init__(self):
        entries,consumptions,statuses=tuple(self.entries),tuple(self.consumptions),tuple(self.governance_statuses)
        for value in entries+consumptions+statuses: _revalidate(value)
        for i,entry in enumerate(entries):
            if entry.sequence != i+1 or entry.previous_entry_identity != (None if i == 0 else entries[i-1].entry_identity):
                raise ValueError("STARTUP_REGISTRY_LINEAGE_INVALID")
        successful_keys=[x.composite_key for x in entries if x.decision == STARTUP_AUTHORIZED]
        rejection_keys=[x.composite_key for x in entries if x.decision == STARTUP_REJECTED]
        consumption_ids=[x.authorization_identity for x in consumptions]
        nonces=[(x.executor_instance_identity,x.executor_session_identity,x.nonce) for x in consumptions]
        if (len(successful_keys) != len(set(successful_keys)) or len(rejection_keys) != len(set(rejection_keys))
                or len(consumption_ids) != len(set(consumption_ids)) or len(nonces) != len(set(nonces))
                or len({x.status_identity for x in statuses}) != len(statuses)):
            raise ValueError("STARTUP_REPLAY_DETECTED")
        authorization_ids={x.authorization.authorization_identity for x in entries if x.authorization}
        if any(x.authorization_identity not in authorization_ids for x in consumptions):
            raise ValueError("STARTUP_CONSUMPTION_NOT_MEMBER")
        predecessors=set()
        if entries: predecessors.add(self._identity(entries[:-1],consumptions,statuses))
        if consumptions: predecessors.add(self._identity(entries,consumptions[:-1],statuses))
        if statuses: predecessors.add(self._identity(entries,consumptions,statuses[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None):
            raise ValueError("STARTUP_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,consumptions,statuses)
        if self.registry_identity and self.registry_identity != expected: raise ValueError("STARTUP_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries); object.__setattr__(self,"consumptions",consumptions)
        object.__setattr__(self,"governance_statuses",statuses); object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,consumptions,statuses):
        return identity_for("PR280_RUNTIME_STARTUP_REGISTRY", {"entries":tuple(x.entry_identity for x in entries),
            "consumptions":tuple(x.consumption_identity for x in consumptions),
            "statuses":tuple(x.status_identity for x in statuses)})
    def append(self,entry,expected_registry_identity,expected_predecessor_identity):
        if expected_registry_identity != self.registry_identity or expected_predecessor_identity != self.previous_registry_identity:
            raise ValueError("STARTUP_REGISTRY_CONFLICT")
        _revalidate(entry)
        if any(x.composite_key == entry.composite_key and x.decision == entry.decision for x in self.entries):
            reason="STARTUP_REPLAY_DETECTED" if entry.decision == STARTUP_AUTHORIZED else "STARTUP_REJECTION_REPLAY"
            raise ValueError(reason)
        return RuntimeStartupRegistry(self.entries+(entry,),self.consumptions,self.governance_statuses,self.registry_identity)
    def apply_status(self,status,expected_registry_identity):
        if expected_registry_identity != self.registry_identity: raise ValueError("STARTUP_REGISTRY_CONFLICT")
        _revalidate(status)
        if any(x.status_identity == status.status_identity for x in self.governance_statuses): raise ValueError("STARTUP_STATUS_REPLAY")
        return RuntimeStartupRegistry(self.entries,self.consumptions,self.governance_statuses+(status,),self.registry_identity)
    def consume(self,consumption,expected_registry_identity):
        if expected_registry_identity != self.registry_identity: raise ValueError("STARTUP_REGISTRY_CONFLICT")
        _revalidate(consumption)
        matches=[x.authorization for x in self.entries if x.authorization and x.authorization.authorization_identity == consumption.authorization_identity]
        if len(matches) != 1: raise ValueError("STARTUP_CONSUMPTION_NOT_MEMBER")
        authorization=matches[0]
        expected=(authorization.executor_identity,authorization.executor_version,authorization.executor_instance_identity,
            authorization.executor_session_identity,authorization.runtime_instance_identity,authorization.activation_generation,
            authorization.authorized_consumer_identity,authorization.expected_consumption_nonce)
        actual=(consumption.executor_identity,consumption.executor_version,consumption.executor_instance_identity,
            consumption.executor_session_identity,consumption.runtime_instance_identity,consumption.activation_generation,
            consumption.consumer_identity,consumption.nonce)
        if actual != expected: raise ValueError("STARTUP_CONSUMER_BINDING_INVALID")
        now=_utc(consumption.consumed_at)
        if not (_utc(authorization.valid_from) <= now < _utc(authorization.expires_at)):
            raise ValueError("STARTUP_AUTHORIZATION_EXPIRED")
        if any(status_applies(x,authorization,consumption.consumed_at) for x in self.governance_statuses):
            raise ValueError("STARTUP_AUTHORIZATION_INVALIDATED")
        if any(x.authorization_identity == consumption.authorization_identity for x in self.consumptions):
            raise ValueError("STARTUP_CONSUMPTION_REPLAY")
        if any((x.executor_instance_identity,x.executor_session_identity,x.nonce) ==
                (consumption.executor_instance_identity,consumption.executor_session_identity,consumption.nonce)
                for x in self.consumptions): raise ValueError("STARTUP_CONSUMPTION_NONCE_REPLAY")
        return RuntimeStartupRegistry(self.entries,self.consumptions+(consumption,),self.governance_statuses,self.registry_identity)
