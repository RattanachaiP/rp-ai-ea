"""Append-only promotion and governance-queue registries."""
from dataclasses import dataclass
from .contracts import GovernanceQueueEntry, PromotionResult
from .identity import identity_for

@dataclass(frozen=True)
class PromotionRegistryEntry:
    result: PromotionResult; sequence:int; previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        PromotionResult(**self.result.__dict__)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("PROMOTION_REGISTRY_ENTRY_INVALID")
        expected=identity_for("PROMOTION_REGISTRY_ENTRY",self.canonical_payload())
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("PROMOTION_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)
    def canonical_payload(self): return {"result_identity":self.result.result_identity,"report_identity":self.result.report.report_identity,
      "approval_request_identity":None if self.result.approval_request is None else self.result.approval_request.request_identity,
      "governance_queue_identity":None if self.result.governance_queue_entry is None else self.result.governance_queue_entry.queue_identity,
      "sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity}

@dataclass(frozen=True)
class PromotionRegistry:
    entries:tuple[PromotionRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,x in enumerate(entries):
            PromotionRegistryEntry(**x.__dict__)
            if x.sequence!=i+1 or x.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("PROMOTION_REGISTRY_LINEAGE_INVALID")
        if len({x.result.result_identity for x in entries})!=len(entries): raise ValueError("DUPLICATE_PROMOTION_DECISION")
        predecessor=None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("PROMOTION_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("PROMOTION_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries): return identity_for("PROMOTION_REGISTRY",tuple(x.entry_identity for x in entries))
    def append(self,result):
        PromotionResult(**result.__dict__)
        for x in self.entries:
            if x.result.result_identity==result.result_identity: return self
            if x.result.report.candidate_identity==result.report.candidate_identity and x.result.report.policy.policy_identity==result.report.policy.policy_identity: raise ValueError("DUPLICATE_PROMOTION_DECISION")
        entry=PromotionRegistryEntry(result,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity)
        return PromotionRegistry(self.entries+(entry,),self.registry_identity)

@dataclass(frozen=True)
class GovernanceQueueRegistryEntry:
    queue_entry:GovernanceQueueEntry; sequence:int; previous_entry_identity:str|None; entry_identity:str=""
    def __post_init__(self):
        GovernanceQueueEntry(**self.queue_entry.__dict__)
        if type(self.sequence)is not int or self.sequence<1 or (self.sequence==1)!=(self.previous_entry_identity is None): raise ValueError("GOVERNANCE_QUEUE_REGISTRY_ENTRY_INVALID")
        expected=identity_for("GOVERNANCE_QUEUE_REGISTRY_ENTRY",{"queue_identity":self.queue_entry.queue_identity,"sequence":self.sequence,"previous_entry_identity":self.previous_entry_identity})
        if self.entry_identity and self.entry_identity!=expected: raise ValueError("GOVERNANCE_QUEUE_REGISTRY_ENTRY_IDENTITY_INVALID")
        object.__setattr__(self,"entry_identity",expected)

@dataclass(frozen=True)
class GovernanceQueueRegistry:
    entries:tuple[GovernanceQueueRegistryEntry,...]=(); previous_registry_identity:str|None=None; registry_identity:str=""
    def __post_init__(self):
        entries=tuple(self.entries); object.__setattr__(self,"entries",entries)
        for i,x in enumerate(entries):
            GovernanceQueueRegistryEntry(**x.__dict__)
            if x.sequence!=i+1 or x.previous_entry_identity!=(None if i==0 else entries[i-1].entry_identity): raise ValueError("GOVERNANCE_QUEUE_REGISTRY_LINEAGE_INVALID")
        if len({x.queue_entry.queue_identity for x in entries})!=len(entries): raise ValueError("DUPLICATE_GOVERNANCE_ENQUEUE")
        predecessor=None if not entries else self._identity(entries[:-1])
        if self.previous_registry_identity!=predecessor: raise ValueError("GOVERNANCE_QUEUE_REGISTRY_PREDECESSOR_INVALID")
        expected=self._identity(entries)
        if self.registry_identity and self.registry_identity!=expected: raise ValueError("GOVERNANCE_QUEUE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self,"registry_identity",expected)
    @staticmethod
    def _identity(entries): return identity_for("GOVERNANCE_QUEUE_REGISTRY",tuple(x.entry_identity for x in entries))
    def append(self,queue_entry):
        GovernanceQueueEntry(**queue_entry.__dict__)
        if any(x.queue_entry.queue_identity==queue_entry.queue_identity for x in self.entries): raise ValueError("DUPLICATE_GOVERNANCE_ENQUEUE")
        entry=GovernanceQueueRegistryEntry(queue_entry,len(self.entries)+1,None if not self.entries else self.entries[-1].entry_identity)
        return GovernanceQueueRegistry(self.entries+(entry,),self.registry_identity)
