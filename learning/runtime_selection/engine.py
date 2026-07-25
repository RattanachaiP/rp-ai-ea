"""PR181 deterministic advisory selection; never scores or applies knowledge."""
from dataclasses import replace
from learning.runtime_knowledge import (RuntimeKnowledgePackage,RuntimeKnowledgePackagingReport,
    RuntimeKnowledgeRepository,RuntimeKnowledgeSnapshot)
from learning.runtime_knowledge.identity import report_uuid as packaging_report_uuid
from .exceptions import RuntimeKnowledgeSelectionError
from .models import (SELECTION_REASONS,RuntimeKnowledgeSelection,
    RuntimeKnowledgeSelectionReport,RuntimeKnowledgeSelectionSnapshot)
from .policy import RuntimeKnowledgeSelectionPolicy
from .repository import RuntimeKnowledgeSelectionRepository

class RuntimeKnowledgeSelector:
    def __init__(self,runtime_repository=None,repository=None,policy=None):
        self.runtime_repository=runtime_repository or RuntimeKnowledgeRepository()
        self.repository=repository or RuntimeKnowledgeSelectionRepository()
        self.policy=policy or RuntimeKnowledgeSelectionPolicy()
        if type(self.runtime_repository) is not RuntimeKnowledgeRepository: raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_REPOSITORY")
        if type(self.repository) is not RuntimeKnowledgeSelectionRepository: raise RuntimeKnowledgeSelectionError("INVALID_SELECTION_REPOSITORY")
        if type(self.policy) is not RuntimeKnowledgeSelectionPolicy: raise RuntimeKnowledgeSelectionError("SELECTION_POLICY_MISMATCH")

    def select(self,source):
        if type(source) not in (RuntimeKnowledgePackage,RuntimeKnowledgeSnapshot,RuntimeKnowledgePackagingReport): raise RuntimeKnowledgeSelectionError("INVALID_RUNTIME_KNOWLEDGE_INPUT")
        packages,generated=self._verify_source(source)
        previous=self.repository.latest_snapshot();existing=self.repository.selections()
        selection_partition=(self.policy.selection_policy_uuid,self.policy.selection_policy_version,self.policy.runtime_selector_version)
        if any((item.selection_policy_uuid,item.selection_policy_version,item.selector_version)!=selection_partition for item in existing):
            raise RuntimeKnowledgeSelectionError("SELECTION_POLICY_MISMATCH")
        snapshot_partition=(self.policy.selection_policy_uuid,self.policy.selection_policy_digest,self.policy.selection_policy_version,self.policy.runtime_selector_version)
        if previous and (previous.selection_policy_uuid,previous.selection_policy_digest,previous.selection_policy_version,previous.selector_version)!=snapshot_partition:
            raise RuntimeKnowledgeSelectionError("SELECTION_POLICY_MISMATCH")
        by_package={item.runtime_package_uuid:item for item in existing};duplicates=0;results=[]
        for package in sorted(packages,key=lambda value:value.runtime_package_uuid):
            state=self._state(package)
            selection=RuntimeKnowledgeSelection.create(runtime_package_uuid=package.runtime_package_uuid,
                runtime_package_digest=package.runtime_package_digest,registry_uuid=package.source_registry_uuid,
                promotion_uuid=package.source_promotion_uuid,validation_uuid=package.source_validation_uuid,
                memory_uuid=package.source_memory_uuid,pattern_uuid=package.source_pattern_uuid,
                knowledge_uuid=package.knowledge_uuid,selection_state=state,selection_reason=SELECTION_REASONS[state],
                selection_policy_uuid=self.policy.selection_policy_uuid,
                selection_policy_version=self.policy.selection_policy_version,
                selector_version=self.policy.runtime_selector_version,created_at=package.generated_at,advisory_only=True)
            prior=by_package.get(package.runtime_package_uuid)
            if prior:
                if prior!=selection: raise RuntimeKnowledgeSelectionError("SELECTION_REPLAY_COLLISION")
                selection=prior;duplicates+=1
            else: self.repository.save(selection);by_package[package.runtime_package_uuid]=selection
            results.append(selection)
        identities=self.repository.identities();repository_digest=self.repository.digest()
        snapshot_values=dict(selection_policy_uuid=self.policy.selection_policy_uuid,selection_policy_digest=self.policy.selection_policy_digest,
            selection_policy_version=self.policy.selection_policy_version,selector_version=self.policy.runtime_selector_version,
            selection_identities=identities,selection_count=len(identities),repository_digest=repository_digest)
        reusable=previous is not None and all(getattr(previous,name)==value for name,value in snapshot_values.items())
        if reusable: snapshot=previous
        else:
            snapshot=RuntimeKnowledgeSelectionSnapshot.create(**snapshot_values,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,generated_at=generated,advisory_only=True)
            self.repository.save_snapshot(snapshot)
        selected=sum(x.selection_state=="SELECTED" for x in results)
        return RuntimeKnowledgeSelectionReport.create(processed_package_count=len(results),selected_count=selected,
            duplicate_count=duplicates,rejected_count=len(results)-selected,repository_digest=repository_digest,
            snapshot_uuid=snapshot.snapshot_uuid,generated_at=generated,advisory_only=True)
    run=select

    def _verify_source(self,source):
        try: packages=self.runtime_repository.packages();snapshots=self.runtime_repository.snapshots();latest=self.runtime_repository.latest_snapshot()
        except Exception as exc: raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGE_PROVENANCE") from exc
        if latest is None: raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGE_PROVENANCE")
        by_package={x.runtime_package_uuid:x for x in packages};by_snapshot={x.snapshot_uuid:x for x in snapshots}
        try: clean=replace(source)
        except (TypeError,ValueError) as exc:
            label={RuntimeKnowledgePackage:"BROKEN_RUNTIME_PACKAGE",RuntimeKnowledgeSnapshot:"SNAPSHOT_MISMATCH",RuntimeKnowledgePackagingReport:"BROKEN_RUNTIME_PACKAGING_REPORT"}[type(source)]
            raise RuntimeKnowledgeSelectionError(label) from exc
        if type(source) is RuntimeKnowledgePackage:
            stored=by_package.get(clean.runtime_package_uuid)
            if stored!=clean or (clean.runtime_package_uuid,clean.runtime_package_digest) not in latest.package_identities: raise RuntimeKnowledgeSelectionError("BROKEN_PACKAGE_PROVENANCE")
            return (clean,),clean.generated_at
        if type(source) is RuntimeKnowledgeSnapshot:
            stored=by_snapshot.get(clean.snapshot_uuid)
            if stored!=clean: raise RuntimeKnowledgeSelectionError("SNAPSHOT_MISMATCH")
            selected=[]
            for identity,content_digest in clean.package_identities:
                package=by_package.get(identity)
                if package is None or package.runtime_package_digest!=content_digest: raise RuntimeKnowledgeSelectionError("SNAPSHOT_MISMATCH")
                selected.append(package)
            return tuple(selected),clean.generated_at
        if packaging_report_uuid(clean.identity_payload())!=clean.report_uuid: raise RuntimeKnowledgeSelectionError("BROKEN_RUNTIME_PACKAGING_REPORT")
        snapshot=by_snapshot.get(clean.snapshot_uuid)
        if snapshot is None or snapshot.snapshot_digest!=clean.snapshot_digest: raise RuntimeKnowledgeSelectionError("SNAPSHOT_MISMATCH")
        if snapshot.repository_digest!=clean.repository_digest: raise RuntimeKnowledgeSelectionError("REPOSITORY_MISMATCH")
        identities=set(snapshot.package_identities)
        for package in clean.runtime_packages:
            if by_package.get(package.runtime_package_uuid)!=package or (package.runtime_package_uuid,package.runtime_package_digest) not in identities: raise RuntimeKnowledgeSelectionError("BROKEN_PACKAGE_PROVENANCE")
        return clean.runtime_packages,clean.generated_at

    def _state(self,package):
        if package.runtime_package_state!=self.policy.minimum_package_integrity or package.source_registry_state!=self.policy.required_registry_state: return "REJECTED"
        if package.source_validation_state!=self.policy.required_validation_state or package.source_promotion_state!=self.policy.required_promotion_state: return "INSUFFICIENT_SELECTION_EVIDENCE"
        return "SELECTED"
