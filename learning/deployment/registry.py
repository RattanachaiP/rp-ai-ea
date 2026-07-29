"""Append-only registry of governance-certified deployment results."""
from dataclasses import dataclass
from learning.promotion.identity import identity_for
from .contracts import DeploymentResult

@dataclass(frozen=True)
class DeploymentRegistryEntry:
    result:DeploymentResult; sequence:int; previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        DeploymentResult(**self.result.__dict__)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("DEPLOYMENT_REGISTRY_ENTRY_INVALID")
        expected=identity_for("DEPLOYMENT_REGISTRY_ENTRY",{"result_identity":self.result.result_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("DEPLOYMENT_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

@dataclass(frozen=True)
class DeploymentRegistry:
    entries:tuple[DeploymentRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,x in enumerate(entries):
            DeploymentRegistryEntry(**x.__dict__)
            if x.sequence!=i+1 or x.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("DEPLOYMENT_REGISTRY_LINEAGE_INVALID")
        if len({x.result.result_identity for x in entries})!=len(entries): raise ValueError("DUPLICATE_DEPLOYMENT_RESULT")
        predecessor=None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("DEPLOYMENT_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("DEPLOYMENT_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries): return identity_for("DEPLOYMENT_REGISTRY",tuple(x.entry_identity for x in entries))
    def append(self,result):
        DeploymentResult(**result.__dict__)
        if result.report.decision!="DEPLOYMENT ELIGIBLE": raise ValueError("DEPLOYMENT_REJECTED_NOT_REGISTRABLE")
        if any(x.result.result_identity==result.result_identity for x in self.entries): return self
        if any(x.result.report.candidate_identity==result.report.candidate_identity for x in self.entries): raise ValueError("DUPLICATE_DEPLOYMENT_CANDIDATE")
        entry=DeploymentRegistryEntry(result,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity)
        return DeploymentRegistry(self.entries+(entry,),self.registry_identity)
