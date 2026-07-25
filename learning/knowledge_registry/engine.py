"""PR179 records offline advisory governance history and grants no operational authority."""
from dataclasses import replace
from learning.common.immutable import thaw
from learning.pattern_promotion.identity import (digest as promotion_digest, promotion_policy_uuid,
    promotion_report_uuid, promotion_uuid)
from learning.pattern_promotion.models import PatternPromotionReport, PromotionRecord
from .exceptions import KnowledgeRegistryError
from .models import KnowledgeRegistryReport, KnowledgeRegistrySnapshot, RegistryRecord
from .registry import RegistryAdmissionPolicy
from .repository import KnowledgeRegistryRepository

class KnowledgeRegistryEngine:
    registry_engine_version = "PR179.2.0"
    def __init__(self, repository=None, policy=None, *, registry_engine_version=None):
        self.repository=repository or KnowledgeRegistryRepository(); self.policy=policy or RegistryAdmissionPolicy()
        self.registry_engine_version=registry_engine_version or type(self).registry_engine_version
        if type(self.policy) is not RegistryAdmissionPolicy: raise KnowledgeRegistryError("INVALID_REGISTRY_ADMISSION_POLICY")
        if not isinstance(self.registry_engine_version,str) or not self.registry_engine_version: raise KnowledgeRegistryError("INVALID_REGISTRY_ENGINE_VERSION")

    def record_admission(self, source):
        if type(source) not in (PromotionRecord,PatternPromotionReport): raise KnowledgeRegistryError("INVALID_PROMOTION_ARTIFACT")
        if type(source) is PatternPromotionReport:
            records=self._validate_report(source); at=source.generated_at
            source_fields=dict(source_artifact_type="PATTERN_PROMOTION_REPORT",source_promotion_uuid=None,source_promotion_digest=None,
                source_promotion_report_uuid=source.report_uuid,source_promotion_report_digest=promotion_digest(source.to_dict()),
                source_promotion_snapshot_uuid=source.snapshot_uuid,source_promotion_snapshot_digest=source.snapshot_digest,
                source_promotion_repository_digest=source.repository_digest)
            engine=source.promotion_engine_version; puid=source.promotion_policy_uuid; pdigest=source.promotion_policy_digest; pversion=source.promotion_policy_version
        else:
            record=self._validate_record(source); records=(record,); at=record.created_at
            source_fields=dict(source_artifact_type="PROMOTION_RECORD",source_promotion_uuid=record.promotion_uuid,
                source_promotion_digest=record.promotion_digest,source_promotion_report_uuid=None,source_promotion_report_digest=None,
                source_promotion_snapshot_uuid=None,source_promotion_snapshot_digest=None,source_promotion_repository_digest=None)
            engine=record.promotion_engine_version; puid=record.promotion_policy_uuid; pdigest=record.promotion_policy_digest; pversion=record.promotion_policy_version
        partition=self._partition(engine,puid,pdigest,pversion)
        existing,previous=self.repository.validate_partition(partition); by_source={x.source_promotion_uuid:x for x in existing}
        output=[]; new=duplicates=0
        for source_record in records:
            state,reasons=self.policy.assess(source_record)
            item=RegistryRecord.create(**partition,**self._provenance(source_record),registry_state=state,
                registry_reasons=reasons,recorded_at=at,advisory_only=True)
            prior=by_source.get(source_record.promotion_uuid)
            if prior:
                if (prior.registry_uuid,prior.registry_digest)!=(item.registry_uuid,item.registry_digest): raise KnowledgeRegistryError("PROMOTION_REPLAY_COLLISION")
                item=prior; duplicates+=1
            else: self.repository.save(item); by_source[source_record.promotion_uuid]=item; new+=1
            output.append(item)
        identities=self.repository.identities(); repo_digest=self.repository.digest()
        if previous and previous.record_identities==identities: snapshot=previous
        else:
            snapshot=KnowledgeRegistrySnapshot.create(**partition,record_identities=identities,record_count=len(identities),repository_digest=repo_digest,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=at,advisory_only=True); self.repository.save_snapshot(snapshot)
        return KnowledgeRegistryReport.create(**source_fields,source_promotion_engine_version=engine,source_promotion_policy_uuid=puid,
            source_promotion_policy_digest=pdigest,source_promotion_policy_version=pversion,
            registry_engine_version=self.registry_engine_version,registry_admission_policy_uuid=self.policy.registry_admission_policy_uuid,
            registry_admission_policy_digest=self.policy.registry_admission_policy_digest,
            registry_admission_policy_version=self.policy.registry_admission_policy_version,registry_records=tuple(output),
            processed_record_count=len(output),new_registry_record_count=new,duplicate_registry_record_count=duplicates,
            advisory_entry_recorded_count=sum(x.registry_state=="ADVISORY_ENTRY_RECORDED" for x in output),
            not_admitted_count=sum(x.registry_state=="NOT_ADMITTED" for x in output),rejected_count=sum(x.registry_state=="REJECTED" for x in output),
            repository_digest=repo_digest,snapshot_uuid=snapshot.snapshot_uuid,snapshot_digest=snapshot.snapshot_digest,generated_at=at,advisory_only=True)
    run=record_admission

    def _partition(self,engine,puid,pdigest,pversion): return dict(registry_engine_version=self.registry_engine_version,
        registry_admission_policy_uuid=self.policy.registry_admission_policy_uuid,
        registry_admission_policy_digest=self.policy.registry_admission_policy_digest,
        registry_admission_policy_version=self.policy.registry_admission_policy_version,
        source_promotion_engine_version=engine,source_promotion_policy_uuid=puid,
        source_promotion_policy_digest=pdigest,source_promotion_policy_version=pversion)
    @staticmethod
    def _provenance(r):
        mapping={"source_promotion_uuid":"promotion_uuid","source_promotion_digest":"promotion_digest",
            "source_promotion_state":"promotion_state","source_promotion_reasons":"promotion_reasons","source_promotion_created_at":"created_at"}
        result={target:thaw(getattr(r,origin)) for target,origin in mapping.items()}
        for name in r.__dataclass_fields__:
            if name.startswith("source_") or name in ("replay_digest","evidence_envelope_uuid","evidence_envelope_digest","knowledge_uuid","knowledge_version","mining_config_digest","outcome_contract","memory_version","memory_state","promotion_policy_thresholds","threshold_monotonicity_result"):
                result.setdefault(name,thaw(getattr(r,name)))
        return result

    @staticmethod
    def _validate_record(record):
        if type(record) is not PromotionRecord: raise KnowledgeRegistryError("INVALID_PROMOTION_ARTIFACT")
        try: r=replace(record)
        except (TypeError,ValueError) as exc: raise KnowledgeRegistryError("BROKEN_PROMOTION_PROVENANCE") from exc
        policy_payload={"promotion_policy_version":r.promotion_policy_version,**thaw(r.promotion_policy_thresholds),"required_validation_state":"STATISTICALLY_CONSISTENT"}
        if promotion_uuid(r.identity_payload())!=r.promotion_uuid or promotion_digest(r.digest_payload())!=r.promotion_digest: raise KnowledgeRegistryError("BROKEN_PROMOTION_PROVENANCE")
        if promotion_policy_uuid(policy_payload)!=r.promotion_policy_uuid or promotion_digest(policy_payload)!=r.promotion_policy_digest: raise KnowledgeRegistryError("BROKEN_PROMOTION_POLICY_IDENTITY")
        source=thaw(r.source_validation_thresholds); promotion=thaw(r.promotion_policy_thresholds)
        if promotion_digest(source)!=r.source_validation_config_digest: raise KnowledgeRegistryError("BROKEN_PROMOTION_THRESHOLDS")
        if any(promotion[k]<source[k] for k in source): raise KnowledgeRegistryError("PROMOTION_THRESHOLD_DOWNGRADE")
        reasons=r.promotion_reasons
        valid=((r.promotion_state=="POLICY_CRITERIA_MET" and "IMMUTABLE_PROMOTION_POLICY_CRITERIA_MET" in reasons)
            or (r.promotion_state=="INSUFFICIENT_PROMOTION_EVIDENCE" and any("INSUFFICIENT" in x or "NOT_MET" in x for x in reasons))
            or (r.promotion_state=="REJECTED" and any("REJECTED" in x for x in reasons)))
        if not valid: raise KnowledgeRegistryError("INVALID_PROMOTION_STATE_REASON_BINDING")
        return r
    @classmethod
    def _validate_report(cls,report):
        try:r=replace(report)
        except (TypeError,ValueError) as exc: raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT") from exc
        if promotion_report_uuid(r.identity_payload())!=r.report_uuid or r.advisory_only is not True: raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT")
        records=tuple(cls._validate_record(x) for x in r.promotion_records)
        if r.processed_record_count!=len(records) or r.new_promotion_count+r.duplicate_promotion_count!=len(records): raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT_REPLAY")
        counts=tuple(sum(x.promotion_state==s for x in records) for s in ("POLICY_CRITERIA_MET","REJECTED","INSUFFICIENT_PROMOTION_EVIDENCE"))
        if counts!=(r.criteria_met_count,r.rejected_count,r.insufficient_promotion_evidence_count): raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT_REPLAY")
        if any(x.promotion_engine_version!=r.promotion_engine_version for x in records): raise KnowledgeRegistryError("MIXED_PROMOTION_ENGINE")
        if any((x.promotion_policy_uuid,x.promotion_policy_digest,x.promotion_policy_version)!=(r.promotion_policy_uuid,r.promotion_policy_digest,r.promotion_policy_version) for x in records): raise KnowledgeRegistryError("MIXED_PROMOTION_POLICY")
        if r.source_artifact_type=="VALIDATION_RECORD":
            if len(records)!=1 or (records[0].source_validation_uuid,records[0].source_validation_digest)!=(r.source_validation_uuid,r.source_validation_digest): raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT_SOURCE")
        elif r.source_artifact_type=="PATTERN_VALIDATION_REPORT":
            if any((x.source_validator_version,x.source_validation_policy_version,x.source_validation_config_digest)!=(r.source_validator_version,r.source_validation_policy_version,r.source_validation_config_digest) for x in records): raise KnowledgeRegistryError("MIXED_PROMOTION_SOURCE")
        else: raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT_SOURCE")
        return records
