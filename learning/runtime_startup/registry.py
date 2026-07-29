"""Immutable append-only CAS registry for PR280 startup outcomes."""
from dataclasses import dataclass
from learning.deployment.contracts import _revalidate, _utc
from learning.promotion.identity import identity_for
from .contracts import RuntimeStartupRegistryEntry, StartupGovernanceStatus, STARTUP_AUTHORIZED

@dataclass(frozen=True)
class RuntimeStartupRegistry:
    entries: tuple[RuntimeStartupRegistryEntry,...]=()
    consumed_authorizations: tuple[tuple[str,str],...]=()
    governance_statuses: tuple[StartupGovernanceStatus,...]=()
    previous_registry_identity: str|None=None
    registry_identity: str=""
    def __post_init__(self):
        entries,consumed,statuses=tuple(self.entries),tuple(tuple(x) for x in self.consumed_authorizations),tuple(self.governance_statuses)
        for value in entries+statuses: _revalidate(value)
        for i,e in enumerate(entries):
            if e.sequence!=i+1 or e.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("STARTUP_REGISTRY_LINEAGE_INVALID")
        successes=[x.composite_key for x in entries if x.decision==STARTUP_AUTHORIZED]
        ids=[x[0] for x in consumed]
        if len(successes)!=len(set(successes)) or len(ids)!=len(set(ids)): raise ValueError("STARTUP_REPLAY_DETECTED")
        for authorization_identity,consumed_at in consumed:
            if not any(x.authorization and x.authorization.authorization_identity==authorization_identity for x in entries): raise ValueError("STARTUP_CONSUMPTION_NOT_MEMBER")
            _utc(consumed_at)
        if len({x.status_identity for x in statuses})!=len(statuses): raise ValueError("STARTUP_STATUS_REPLAY")
        predecessors=set()
        if entries: predecessors.add(self._identity(entries[:-1],consumed,statuses))
        if consumed: predecessors.add(self._identity(entries,consumed[:-1],statuses))
        if statuses: predecessors.add(self._identity(entries,consumed,statuses[:-1]))
        if (self.previous_registry_identity not in predecessors if predecessors else self.previous_registry_identity is not None): raise ValueError("STARTUP_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries,consumed,statuses)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("STARTUP_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entries",entries); object.__setattr__(self,"consumed_authorizations",consumed); object.__setattr__(self,"governance_statuses",statuses); object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries,consumed,statuses): return identity_for("PR280_RUNTIME_STARTUP_REGISTRY",{"entries":tuple(x.entry_identity for x in entries),"consumed":consumed,"statuses":tuple(x.status_identity for x in statuses)})
    def append(self,entry,expected_registry_identity,expected_predecessor_identity):
        if expected_registry_identity!=self.registry_identity or expected_predecessor_identity!=self.previous_registry_identity: raise ValueError("STARTUP_REGISTRY_CONFLICT")
        _revalidate(entry)
        if entry.decision==STARTUP_AUTHORIZED and any(x.decision==STARTUP_AUTHORIZED and x.composite_key==entry.composite_key for x in self.entries): raise ValueError("STARTUP_REPLAY_DETECTED")
        return RuntimeStartupRegistry(self.entries+(entry,),self.consumed_authorizations,self.governance_statuses,self.registry_identity)
    def apply_status(self,status,expected_registry_identity):
        if expected_registry_identity!=self.registry_identity: raise ValueError("STARTUP_REGISTRY_CONFLICT")
        _revalidate(status)
        authorization_ids={x.authorization.authorization_identity for x in self.entries if x.authorization}
        if status.subject_identity not in authorization_ids and status.subject_identity!="GLOBAL": raise ValueError("STARTUP_STATUS_SUBJECT_NOT_MEMBER")
        if any(x.status_identity==status.status_identity for x in self.governance_statuses): raise ValueError("STARTUP_STATUS_REPLAY")
        return RuntimeStartupRegistry(self.entries,self.consumed_authorizations,self.governance_statuses+(status,),self.registry_identity)
    def consume(self,authorization_identity,consumed_at,expected_registry_identity):
        if expected_registry_identity!=self.registry_identity: raise ValueError("STARTUP_REGISTRY_CONFLICT")
        matches=[x.authorization for x in self.entries if x.authorization and x.authorization.authorization_identity==authorization_identity]
        if len(matches)!=1 or any(x[0]==authorization_identity for x in self.consumed_authorizations): raise ValueError("STARTUP_CONSUMPTION_REPLAY")
        authorization=matches[0]; now=_utc(consumed_at)
        if not (_utc(authorization.valid_from)<=now<_utc(authorization.expires_at)): raise ValueError("STARTUP_AUTHORIZATION_EXPIRED")
        if any(x.subject_identity in {authorization_identity,"GLOBAL"} and _utc(x.effective_at)<=now for x in self.governance_statuses):
            raise ValueError("STARTUP_AUTHORIZATION_INVALIDATED")
        return RuntimeStartupRegistry(self.entries,self.consumed_authorizations+((authorization_identity,consumed_at),),self.governance_statuses,self.registry_identity)
