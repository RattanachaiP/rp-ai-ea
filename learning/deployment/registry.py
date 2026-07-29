"""Append-only registry with composite deployment lineage and explicit supersession."""
from dataclasses import dataclass
from learning.promotion.identity import identity_for
from .contracts import DeploymentResult, _revalidate

@dataclass(frozen=True)
class DeploymentRegistryEntry:
    result:DeploymentResult; sequence:int; previous_entry_identity:str|None
    supersedes_entry_identity:str|None=None; entry_identity:str=""
    def __post_init__(self):
        _revalidate(self.result)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("DEPLOYMENT_REGISTRY_ENTRY_INVALID")
        expected=identity_for("DEPLOYMENT_REGISTRY_ENTRY",self.canonical_payload())
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("DEPLOYMENT_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)
    def canonical_payload(self): return {"result_identity":self.result.result_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity,"supersedes_entry_identity":self.supersedes_entry_identity}
    @property
    def composite_key(self):
        r=self.result.report
        return (r.candidate_identity,r.artifact_identity,r.target_environment_identity,r.runtime_contract_identity,r.deployment_policy_identity)

@dataclass(frozen=True)
class DeploymentRegistry:
    entries:tuple[DeploymentRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,x in enumerate(entries):
            DeploymentRegistryEntry(**x.__dict__)
            if x.sequence!=i+1 or x.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("DEPLOYMENT_REGISTRY_LINEAGE_INVALID")
            if x.supersedes_entry_identity and not any(y.entry_identity==x.supersedes_entry_identity and y.composite_key==x.composite_key for y in entries[:i]): raise ValueError("DEPLOYMENT_REGISTRY_SUPERSESSION_INVALID")
        if len({x.result.result_identity for x in entries})!=len(entries): raise ValueError("DUPLICATE_DEPLOYMENT_RESULT")
        predecessor=None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("DEPLOYMENT_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("DEPLOYMENT_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries): return identity_for("DEPLOYMENT_REGISTRY",tuple(x.entry_identity for x in entries))
    def append(self,result,supersedes_entry_identity=None):
        _revalidate(result)
        if result.report.decision!="DEPLOYMENT GOVERNANCE ELIGIBLE": raise ValueError("DEPLOYMENT_REJECTED_NOT_REGISTRABLE")
        key=(result.report.candidate_identity,result.report.artifact_identity,result.report.target_environment_identity,result.report.runtime_contract_identity,result.report.deployment_policy_identity)
        prior=[x for x in self.entries if x.composite_key==key]
        if any(x.result.result_identity==result.result_identity for x in self.entries): return self
        if prior and supersedes_entry_identity!=prior[-1].entry_identity: raise ValueError("DEPLOYMENT_COMPOSITE_KEY_REQUIRES_SUPERSESSION")
        entry=DeploymentRegistryEntry(result,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity,supersedes_entry_identity)
        return DeploymentRegistry(self.entries+(entry,),self.registry_identity)
