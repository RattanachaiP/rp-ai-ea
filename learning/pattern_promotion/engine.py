"""PR178 eligibility engine; it never publishes or activates patterns."""
from dataclasses import replace
from learning.pattern_validation.identity import digest as validation_digest, validation_report_uuid, validation_uuid
from learning.pattern_validation.models import PatternValidationReport, ValidationRecord
from .exceptions import PatternPromotionError
from .models import PatternPromotionReport, PatternPromotionSnapshot, PromotionRecord
from .promotion_policy import PromotionPolicy
from .repository import PatternPromotionRepository


class PatternPromotionEngine:
    def __init__(self, repository=None, policy=None):
        self.repository = repository or PatternPromotionRepository()
        self.policy = policy or PromotionPolicy()
        if not isinstance(self.policy, PromotionPolicy): raise PatternPromotionError("INVALID_PROMOTION_POLICY")

    def promote(self, source):
        if type(source) not in (ValidationRecord, PatternValidationReport):
            raise PatternPromotionError("INVALID_VALIDATION_INPUT")
        records = self._validate_report(source) if type(source) is PatternValidationReport else (self._validate_record(source),)
        generated_at = source.generated_at if type(source) is PatternValidationReport else source.validated_at
        previous = self.repository.latest_snapshot()
        if previous and previous.record_identities != self.repository.identities():
            raise PatternPromotionError("PROMOTION_REPOSITORY_SNAPSHOT_MISMATCH")
        existing = {x.promotion_uuid: x for x in self.repository.records()}; output = []
        for source_record in records:
            state, reasons = self.policy.assess(source_record)
            record = PromotionRecord.create(validation_uuid=source_record.validation_uuid,
                validation_digest=source_record.validation_digest, memory_uuid=source_record.source_memory_uuid,
                pattern_uuid=source_record.source_pattern_uuid, policy_uuid=self.policy.policy_uuid,
                knowledge_uuid=source_record.knowledge_uuid, promotion_state=state,
                promotion_reasons=reasons, promotion_policy_version=self.policy.promotion_policy_version,
                created_at=generated_at, advisory_only=True)
            prior = existing.get(record.promotion_uuid)
            if prior and prior.promotion_digest != record.promotion_digest:
                raise PatternPromotionError("DUPLICATE_PROMOTION_HISTORY")
            if not prior: self.repository.save(record); existing[record.promotion_uuid] = record
            output.append(record)
        identities = self.repository.identities()
        snapshot = previous if previous and previous.record_identities == identities else \
            PatternPromotionSnapshot.create(identities, previous, generated_at)
        if snapshot is not previous: self.repository.save_snapshot(snapshot)
        return PatternPromotionReport.create(promotion_records=tuple(output),
            eligible_count=sum(x.promotion_state == "PROMOTION_ELIGIBLE" for x in output),
            rejected_count=sum(x.promotion_state == "REJECTED" for x in output),
            pending_count=sum(x.promotion_state == "NOT_YET_ELIGIBLE" for x in output),
            repository_digest=self.repository.digest(), generated_at=generated_at, advisory_only=True)

    run = promote

    @staticmethod
    def _validate_record(record):
        if type(record) is not ValidationRecord:
            raise PatternPromotionError("INVALID_VALIDATION_INPUT")
        try: reconstructed = replace(record)
        except (TypeError, ValueError) as exc:
            raise PatternPromotionError("BROKEN_VALIDATION_PROVENANCE") from exc
        if (validation_uuid(reconstructed.identity_payload()) != reconstructed.validation_uuid
                or validation_digest(reconstructed.digest_payload()) != reconstructed.validation_digest
                or reconstructed.advisory_only is not True or reconstructed.memory_state != "STORED"):
            raise PatternPromotionError("BROKEN_VALIDATION_PROVENANCE")
        required = {"sample_count": int, "support": (int, float), "confidence": (int, float),
                    "expectancy": (int, float)}
        stats = dict(reconstructed.validation_statistics)
        if any(name not in stats or not isinstance(stats[name], kind) or isinstance(stats[name], bool)
               for name, kind in required.items()):
            raise PatternPromotionError("BROKEN_VALIDATION_STATISTICS")
        return reconstructed

    @classmethod
    def _validate_report(cls, report):
        try: reconstructed = replace(report)
        except (TypeError, ValueError) as exc: raise PatternPromotionError("BROKEN_VALIDATION_REPORT") from exc
        if validation_report_uuid(reconstructed.identity_payload()) != reconstructed.report_uuid:
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_PROVENANCE")
        return tuple(cls._validate_record(x) for x in reconstructed.validation_records)
