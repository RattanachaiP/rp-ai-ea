"""PR182 advisory confidence evaluation; no decision or Runtime authority."""
from dataclasses import replace
from learning.runtime_selection import KnowledgeEligibilityRecord, KnowledgeEligibilityReport, KnowledgeEligibilitySnapshot, RuntimeKnowledgeSelectionRepository
from learning.runtime_selection.exceptions import RuntimeKnowledgeSelectionError
from .exceptions import RuntimeConfidenceError
from .models import ConfidenceRecord, ConfidenceSnapshot, RuntimeConfidenceReport
from .policy import RuntimeConfidencePolicy
from .repository import RuntimeConfidenceRepository

class RuntimeConfidenceEvaluator:
    def __init__(self, eligibility_repository=None, repository=None, policy=None):
        self.eligibility_repository=eligibility_repository or RuntimeKnowledgeSelectionRepository()
        self.repository=repository or RuntimeConfidenceRepository(); self.policy=policy or RuntimeConfidencePolicy()
        if type(self.eligibility_repository) is not RuntimeKnowledgeSelectionRepository: raise RuntimeConfidenceError("INVALID_ELIGIBILITY")
        if type(self.repository) is not RuntimeConfidenceRepository: raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        if type(self.policy) is not RuntimeConfidencePolicy: raise RuntimeConfidenceError("POLICY_MISMATCH")

    def evaluate_confidence(self,source):
        if type(source) not in (KnowledgeEligibilityRecord,KnowledgeEligibilityReport,KnowledgeEligibilitySnapshot): raise RuntimeConfidenceError("INVALID_ELIGIBILITY")
        records,generated=self._verify(source); partition=self._partition()
        present=self.repository.records()
        if present and any(tuple(getattr(x,n) for n in ("confidence_policy_uuid","confidence_policy_digest","confidence_policy_version")) != tuple(partition[n] for n in ("confidence_policy_uuid","confidence_policy_digest","confidence_policy_version")) for x in present): raise RuntimeConfidenceError("POLICY_MISMATCH")
        existing,previous=self.repository.validate_partition(partition); by={x.eligibility_uuid:x for x in existing}
        output=[]; duplicates=0
        for eligibility in sorted(records,key=lambda x:x.selection_uuid):
            state,reason,score=self._classify(eligibility)
            record=ConfidenceRecord.create(**partition,eligibility_uuid=eligibility.selection_uuid,eligibility_digest=eligibility.selection_digest,
                runtime_package_uuid=eligibility.source_runtime_package_uuid,registry_uuid=eligibility.source_registry_uuid,promotion_uuid=eligibility.source_promotion_uuid,
                validation_uuid=eligibility.source_validation_uuid,memory_uuid=eligibility.source_memory_uuid,pattern_uuid=eligibility.source_pattern_uuid,
                knowledge_uuid=eligibility.knowledge_uuid,confidence_state=state,confidence_reason=reason,confidence_score=score,created_at=eligibility.created_at,advisory_only=True)
            prior=by.get(eligibility.selection_uuid)
            if prior is not None:
                if prior!=record: raise RuntimeConfidenceError("REPLAY_COLLISION")
                record=prior; duplicates+=1
            else: self.repository.save(record); by[eligibility.selection_uuid]=record
            output.append(record)
        identities=self.repository.identities(); repo_digest=self.repository.digest(); values={**partition,"confidence_identities":identities,"record_count":len(identities),"repository_digest":repo_digest}
        reusable=previous is not None and all(getattr(previous,n)==v for n,v in values.items())
        if reusable: snapshot=previous
        else:
            snapshot=ConfidenceSnapshot.create(**values,previous_snapshot_uuid=previous.snapshot_uuid if previous else None,previous_snapshot_digest=previous.snapshot_digest if previous else None,generated_at=generated,advisory_only=True); self.repository.save_snapshot(snapshot)
        return RuntimeConfidenceReport.create(**partition,confidence_records=tuple(output),processed_record_count=len(output),
            confidence_evaluated_count=sum(x.confidence_state=="CONFIDENCE_EVALUATED" for x in output),insufficient_confidence_count=sum(x.confidence_state=="INSUFFICIENT_CONFIDENCE_EVIDENCE" for x in output),
            rejected_count=sum(x.confidence_state=="REJECTED" for x in output),duplicate_count=duplicates,repository_digest=repo_digest,snapshot_uuid=snapshot.snapshot_uuid,snapshot_digest=snapshot.snapshot_digest,generated_at=generated,advisory_only=True)
    run=evaluate_confidence

    def _verify(self,source):
        try: stored=self.eligibility_repository.selections(); snapshots=self.eligibility_repository.snapshots(); latest=self.eligibility_repository.latest_snapshot()
        except RuntimeKnowledgeSelectionError as exc: raise RuntimeConfidenceError("BROKEN_PROVENANCE") from exc
        if type(source) is KnowledgeEligibilityReport:
            if latest is None or source.selection_snapshot_uuid!=latest.snapshot_uuid or source.selection_snapshot_digest!=latest.snapshot_digest: raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
            if source.repository_digest!=self.eligibility_repository.digest(): raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        try: clean=replace(source)
        except (TypeError,ValueError) as exc: raise RuntimeConfidenceError("BROKEN_PROVENANCE") from exc
        by={x.selection_uuid:x for x in stored}
        if type(clean) is KnowledgeEligibilityRecord:
            if by.get(clean.selection_uuid)!=clean: raise RuntimeConfidenceError("BROKEN_PROVENANCE")
            members=[s for s in snapshots if (clean.selection_uuid,clean.selection_digest) in s.selection_identities]
            if not members: raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
            return (clean,),clean.created_at
        if type(clean) is KnowledgeEligibilitySnapshot:
            match=next((s for s in snapshots if s.snapshot_uuid==clean.snapshot_uuid),None)
            if match!=clean: raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
            selected=[]
            for uid,dig in clean.selection_identities:
                item=by.get(uid)
                if item is None or item.selection_digest!=dig: raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
                selected.append(item)
            return tuple(selected),clean.generated_at
        if clean.processed_package_count!=len(clean.runtime_selections) or clean.new_selection_count+clean.duplicate_selection_count!=len(clean.runtime_selections): raise RuntimeConfidenceError("INVALID_ELIGIBILITY")
        if latest is None or clean.selection_snapshot_uuid!=latest.snapshot_uuid or clean.selection_snapshot_digest!=latest.snapshot_digest: raise RuntimeConfidenceError("SNAPSHOT_MISMATCH")
        if clean.repository_digest!=self.eligibility_repository.digest(): raise RuntimeConfidenceError("REPOSITORY_MISMATCH")
        if any(by.get(x.selection_uuid)!=x or (x.selection_uuid,x.selection_digest) not in latest.selection_identities for x in clean.runtime_selections): raise RuntimeConfidenceError("BROKEN_PROVENANCE")
        return clean.runtime_selections,clean.generated_at

    def _partition(self):
        if self.policy.confidence_engine_version!="PR182.1.0": raise RuntimeConfidenceError("ENGINE_VERSION_MISMATCH")
        return {"confidence_policy_uuid":self.policy.confidence_policy_uuid,"confidence_policy_digest":self.policy.confidence_policy_digest,"confidence_policy_version":self.policy.confidence_policy_version,"confidence_engine_version":self.policy.confidence_engine_version}
    @staticmethod
    def _classify(item):
        if item.selection_state=="REJECTED": return "REJECTED","INVALID_ELIGIBILITY",0.0
        if item.selection_state=="INSUFFICIENT_SELECTION_EVIDENCE": return "INSUFFICIENT_CONFIDENCE_EVIDENCE","INSUFFICIENT_ELIGIBILITY_EVIDENCE",0.0
        return "CONFIDENCE_EVALUATED","ADVISORY_CONFIDENCE_EVALUATED",1.0
