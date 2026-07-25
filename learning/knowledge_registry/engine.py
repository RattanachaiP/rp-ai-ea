"""PR179 immutable registry admission only; grants no runtime authority."""
from dataclasses import replace
from learning.pattern_promotion.identity import digest as promotion_digest, promotion_report_uuid, promotion_uuid
from learning.pattern_promotion.models import PatternPromotionReport, PromotionRecord
from .exceptions import KnowledgeRegistryError
from .models import KnowledgeRegistryReport, KnowledgeRegistrySnapshot, RegistryRecord
from .registry import admission_result
from .repository import KnowledgeRegistryRepository


class KnowledgeRegistryEngine:
    registry_version = "PR179.1.0"

    def __init__(self, repository=None, *, registry_version=None):
        self.repository = repository or KnowledgeRegistryRepository()
        self.registry_version = registry_version or type(self).registry_version
        if not isinstance(self.registry_version, str) or not self.registry_version:
            raise KnowledgeRegistryError("INVALID_REGISTRY_VERSION")

    def admit(self, source):
        if type(source) not in (PromotionRecord, PatternPromotionReport):
            raise KnowledgeRegistryError("INVALID_PROMOTION_ARTIFACT")
        if type(source) is PatternPromotionReport:
            records = self._validate_report(source); generated_at = source.generated_at
            source_type = "PATTERN_PROMOTION_REPORT"; source_uuid = source.report_uuid
            source_digest = promotion_digest(source.to_dict())
            engine_version = source.promotion_engine_version
            policy_uuid = source.promotion_policy_uuid; policy_digest = source.promotion_policy_digest
        else:
            record = self._validate_record(source); records = (record,); generated_at = record.created_at
            source_type = "PROMOTION_RECORD"; source_uuid = source_digest = None
            engine_version = record.promotion_engine_version
            policy_uuid = record.promotion_policy_uuid; policy_digest = record.promotion_policy_digest

        existing_records, previous = self.repository.validate_partition(
            self.registry_version, engine_version, policy_uuid, policy_digest)
        existing_by_promotion = {x.promotion_uuid: x for x in existing_records}
        output, duplicates = [], 0
        for promotion in records:
            state, reasons = admission_result(promotion.promotion_state)
            item = RegistryRecord.create(promotion_uuid=promotion.promotion_uuid,
                promotion_digest=promotion.promotion_digest,
                validation_uuid=promotion.source_validation_uuid,
                memory_uuid=promotion.source_memory_uuid, pattern_uuid=promotion.source_pattern_uuid,
                knowledge_uuid=promotion.knowledge_uuid, registry_version=self.registry_version,
                registry_state=state, registry_reasons=reasons, registered_at=generated_at,
                advisory_only=True)
            prior = existing_by_promotion.get(promotion.promotion_uuid)
            if prior:
                if prior.registry_uuid != item.registry_uuid or prior.registry_digest != item.registry_digest:
                    raise KnowledgeRegistryError("PROMOTION_REPLAY_COLLISION")
                duplicates += 1; item = prior
            else:
                self.repository.save(item); existing_by_promotion[promotion.promotion_uuid] = item
            output.append(item)

        identities = self.repository.identities(); repository_digest = self.repository.digest()
        if previous and previous.record_identities == identities:
            snapshot = previous
        else:
            snapshot = KnowledgeRegistrySnapshot.create(registry_version=self.registry_version,
                promotion_engine_version=engine_version, promotion_policy_uuid=policy_uuid,
                promotion_policy_digest=policy_digest, record_identities=identities,
                repository_digest=repository_digest,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at, advisory_only=True)
            self.repository.save_snapshot(snapshot)
        return KnowledgeRegistryReport.create(source_artifact_type=source_type,
            source_report_uuid=source_uuid, source_report_digest=source_digest,
            promotion_engine_version=engine_version, promotion_policy_uuid=policy_uuid,
            promotion_policy_digest=policy_digest, registry_records=tuple(output),
            registered_count=sum(x.registry_state == "REGISTERED" for x in output),
            rejected_count=sum(x.registry_state != "REGISTERED" for x in output),
            duplicate_count=duplicates, repository_digest=repository_digest,
            snapshot_uuid=snapshot.snapshot_uuid, generated_at=generated_at, advisory_only=True)

    run = admit

    @staticmethod
    def _validate_record(record):
        if type(record) is not PromotionRecord:
            raise KnowledgeRegistryError("INVALID_PROMOTION_ARTIFACT")
        try: reconstructed = replace(record)
        except (TypeError, ValueError) as exc:
            raise KnowledgeRegistryError("BROKEN_PROMOTION_PROVENANCE") from exc
        if (promotion_uuid(reconstructed.identity_payload()) != reconstructed.promotion_uuid
                or promotion_digest(reconstructed.digest_payload()) != reconstructed.promotion_digest
                or reconstructed.advisory_only is not True
                or reconstructed.memory_state != "STORED"
                or reconstructed.threshold_monotonicity_result != "PASSED"):
            raise KnowledgeRegistryError("BROKEN_PROMOTION_PROVENANCE")
        return reconstructed

    @classmethod
    def _validate_report(cls, report):
        try: reconstructed = replace(report)
        except (TypeError, ValueError) as exc:
            raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT") from exc
        if (promotion_report_uuid(reconstructed.identity_payload()) != reconstructed.report_uuid
                or reconstructed.advisory_only is not True):
            raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT")
        records = tuple(cls._validate_record(x) for x in reconstructed.promotion_records)
        if (reconstructed.processed_record_count != len(records)
                or reconstructed.new_promotion_count + reconstructed.duplicate_promotion_count != len(records)):
            raise KnowledgeRegistryError("BROKEN_PROMOTION_REPLAY")
        counts = tuple(sum(x.promotion_state == state for x in records) for state in
                       ("POLICY_CRITERIA_MET", "REJECTED", "INSUFFICIENT_PROMOTION_EVIDENCE"))
        if counts != (reconstructed.criteria_met_count, reconstructed.rejected_count,
                      reconstructed.insufficient_promotion_evidence_count):
            raise KnowledgeRegistryError("BROKEN_PROMOTION_REPORT")
        if any((x.promotion_engine_version != reconstructed.promotion_engine_version
                or x.promotion_policy_uuid != reconstructed.promotion_policy_uuid
                or x.promotion_policy_digest != reconstructed.promotion_policy_digest
                or x.promotion_policy_version != reconstructed.promotion_policy_version) for x in records):
            raise KnowledgeRegistryError("MIXED_PROMOTION_POLICY")
        return records
