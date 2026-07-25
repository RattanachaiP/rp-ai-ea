"""PR178 policy assessment only; no publication or operational authority."""
from dataclasses import replace
from math import isfinite
from collections.abc import Mapping
from learning.common.immutable import thaw
from learning.pattern_memory.models import json_safe, valid_digest, valid_uuid
from learning.pattern_validation.identity import digest as validation_digest, validation_report_uuid, validation_uuid
from learning.pattern_validation.models import PatternValidationReport, ValidationRecord
from .exceptions import PatternPromotionError
from .models import PatternPromotionReport, PatternPromotionSnapshot, PromotionRecord
from .promotion_policy import PromotionPolicy
from .repository import PatternPromotionRepository

_THRESHOLD_FIELDS = ("minimum_sample_count", "minimum_support", "minimum_confidence", "minimum_expectancy")


class PatternPromotionEngine:
    promotion_engine_version = "PR178.2.0"

    def __init__(self, repository=None, policy=None, *, promotion_engine_version=None):
        self.repository = repository or PatternPromotionRepository()
        self.policy = policy or PromotionPolicy()
        self.promotion_engine_version = promotion_engine_version or type(self).promotion_engine_version
        if not isinstance(self.policy, PromotionPolicy): raise PatternPromotionError("INVALID_PROMOTION_POLICY")
        if not isinstance(self.promotion_engine_version, str) or not self.promotion_engine_version:
            raise PatternPromotionError("INVALID_PROMOTION_ENGINE_VERSION")

    def assess(self, source):
        if type(source) not in (ValidationRecord, PatternValidationReport):
            raise PatternPromotionError("INVALID_VALIDATION_INPUT")
        if type(source) is PatternValidationReport:
            records = self._validate_report(source); generated_at = source.generated_at
            source_fields = dict(source_artifact_type="PATTERN_VALIDATION_REPORT",
                source_validation_report_uuid=source.report_uuid,
                source_validation_report_digest=validation_digest(source.to_dict()),
                source_validation_snapshot_uuid=source.snapshot_uuid,
                source_validation_snapshot_digest=source.snapshot_digest,
                source_validation_repository_digest=source.repository_digest,
                source_validation_uuid=None, source_validation_digest=None,
                source_validator_version=source.validator_version,
                source_validation_policy_version=source.validation_policy_version,
                source_validation_config_digest=source.validation_config_digest)
        else:
            record = self._validate_record(source); records = (record,); generated_at = record.validated_at
            source_fields = dict(source_artifact_type="VALIDATION_RECORD",
                source_validation_report_uuid=None, source_validation_report_digest=None,
                source_validation_snapshot_uuid=None, source_validation_snapshot_digest=None,
                source_validation_repository_digest=None, source_validation_uuid=record.validation_uuid,
                source_validation_digest=record.validation_digest, source_validator_version=record.validator_version,
                source_validation_policy_version=record.validation_policy_version,
                source_validation_config_digest=record.validation_config_digest)
        existing_records, previous = self.repository.validate_partition(self.promotion_engine_version, self.policy)
        existing = {x.promotion_uuid: x for x in existing_records}
        output, new_count, duplicate_count = [], 0, 0
        for source_record in records:
            thresholds = self._validate_thresholds(source_record)
            state, reasons = self.policy.assess(source_record)
            item = PromotionRecord.create(**self._record_values(source_record, thresholds, state, reasons, generated_at))
            prior = existing.get(item.promotion_uuid)
            if prior:
                if prior.promotion_digest != item.promotion_digest:
                    raise PatternPromotionError("DUPLICATE_PROMOTION_HISTORY")
                duplicate_count += 1
            else:
                self.repository.save(item); existing[item.promotion_uuid] = item; new_count += 1
            output.append(item)
        identities = self.repository.identities()
        snapshot = previous if previous and previous.record_identities == identities else \
            PatternPromotionSnapshot.create(self.promotion_engine_version, self.policy, identities,
                                            previous, generated_at)
        if snapshot is not previous: self.repository.save_snapshot(snapshot)
        return PatternPromotionReport.create(**source_fields,
            promotion_engine_version=self.promotion_engine_version,
            promotion_policy_uuid=self.policy.policy_uuid, promotion_policy_digest=self.policy.policy_digest,
            promotion_policy_version=self.policy.promotion_policy_version, promotion_records=tuple(output),
            processed_record_count=len(output), new_promotion_count=new_count,
            duplicate_promotion_count=duplicate_count,
            criteria_met_count=sum(x.promotion_state == "POLICY_CRITERIA_MET" for x in output),
            rejected_count=sum(x.promotion_state == "REJECTED" for x in output),
            insufficient_promotion_evidence_count=sum(x.promotion_state ==
                "INSUFFICIENT_PROMOTION_EVIDENCE" for x in output),
            repository_digest=self.repository.digest(), snapshot_uuid=snapshot.snapshot_uuid,
            snapshot_digest=snapshot.snapshot_digest, generated_at=generated_at, advisory_only=True)

    run = assess

    @staticmethod
    def _validate_record(record):
        if type(record) is not ValidationRecord: raise PatternPromotionError("INVALID_VALIDATION_INPUT")
        try: reconstructed = replace(record)
        except (TypeError, ValueError) as exc: raise PatternPromotionError("BROKEN_VALIDATION_PROVENANCE") from exc
        if (validation_uuid(reconstructed.identity_payload()) != reconstructed.validation_uuid
                or validation_digest(reconstructed.digest_payload()) != reconstructed.validation_digest
                or reconstructed.advisory_only is not True or reconstructed.memory_state != "STORED"):
            raise PatternPromotionError("BROKEN_VALIDATION_PROVENANCE")
        PatternPromotionEngine._validate_statistics(reconstructed)
        return reconstructed

    @staticmethod
    def _validate_statistics(record):
        statistics = thaw(record.validation_statistics)
        if (not isinstance(statistics, dict) or not all(isinstance(k, str) for k in statistics)
                or not json_safe(statistics)):
            raise PatternPromotionError("BROKEN_VALIDATION_STATISTICS")
        def finite_tree(value):
            if isinstance(value, dict): return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
            if isinstance(value, list): return all(finite_tree(v) for v in value)
            return not isinstance(value, float) or isfinite(value)
        if not finite_tree(statistics): raise PatternPromotionError("BROKEN_VALIDATION_STATISTICS")
        if (not isinstance(statistics.get("sample_count"), int) or isinstance(statistics.get("sample_count"), bool)
                or any(not isinstance(statistics.get(x), (int, float)) or isinstance(statistics.get(x), bool)
                       or not isfinite(statistics[x]) for x in ("support", "confidence", "expectancy"))):
            raise PatternPromotionError("BROKEN_VALIDATION_STATISTICS")
        thresholds = statistics.get("thresholds")
        if not isinstance(thresholds, dict) or set(thresholds) != set(_THRESHOLD_FIELDS):
            raise PatternPromotionError("MALFORMED_VALIDATION_THRESHOLDS")
        if (not isinstance(thresholds["minimum_sample_count"], int)
                or isinstance(thresholds["minimum_sample_count"], bool)
                or any(not isinstance(thresholds[x], (int, float)) or isinstance(thresholds[x], bool)
                       or not isfinite(thresholds[x]) for x in _THRESHOLD_FIELDS[1:])):
            raise PatternPromotionError("MALFORMED_VALIDATION_THRESHOLDS")
        if validation_digest(thresholds) != record.validation_config_digest:
            raise PatternPromotionError("VALIDATION_CONFIG_DIGEST_MISMATCH")

    def _validate_thresholds(self, record):
        thresholds = thaw(record.validation_statistics)["thresholds"]
        if any(self.policy.thresholds[name] < thresholds[name] for name in _THRESHOLD_FIELDS):
            raise PatternPromotionError("PROMOTION_POLICY_DOWNGRADE")
        return thresholds

    @classmethod
    def _validate_report(cls, report):
        if not valid_uuid(report.snapshot_uuid) or not valid_digest(report.snapshot_digest):
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_SNAPSHOT")
        if not valid_digest(report.repository_digest):
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_REPOSITORY")
        try: reconstructed = replace(report)
        except (TypeError, ValueError) as exc: raise PatternPromotionError("BROKEN_VALIDATION_REPORT") from exc
        if validation_report_uuid(reconstructed.identity_payload()) != reconstructed.report_uuid:
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_PROVENANCE")
        if reconstructed.advisory_only is not True:
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_PROVENANCE")
        records = tuple(cls._validate_record(x) for x in reconstructed.validation_records)
        if reconstructed.processed_record_count != len(records): raise PatternPromotionError("BROKEN_VALIDATION_REPORT")
        if reconstructed.new_validation_count + reconstructed.duplicate_validation_count != len(records):
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT")
        counts = tuple(sum(x.validation_state == state for x in records) for state in
                       ("STATISTICALLY_CONSISTENT", "INVALID", "INSUFFICIENT_EVIDENCE"))
        if counts != (reconstructed.statistically_consistent_count, reconstructed.invalid_count,
                      reconstructed.insufficient_count): raise PatternPromotionError("BROKEN_VALIDATION_REPORT")
        if any(x.validator_version != reconstructed.validator_version for x in records):
            raise PatternPromotionError("MIXED_VALIDATOR_VERSION")
        if any(x.validation_policy_version != reconstructed.validation_policy_version for x in records):
            raise PatternPromotionError("MIXED_VALIDATION_POLICY")
        if any(x.validation_config_digest != reconstructed.validation_config_digest for x in records):
            raise PatternPromotionError("MIXED_VALIDATION_CONFIG")
        if reconstructed.source_artifact_type == "PATTERN_MEMORY_RECORD":
            if (len(records) != 1 or records[0].source_memory_uuid != reconstructed.source_memory_uuid
                    or records[0].source_memory_digest != reconstructed.source_memory_digest):
                raise PatternPromotionError("BROKEN_VALIDATION_REPORT_SOURCE")
        elif reconstructed.source_artifact_type != "PATTERN_MEMORY_REPORT":
            raise PatternPromotionError("BROKEN_VALIDATION_REPORT_SOURCE")
        identities = {(x.policy_uuid, x.policy_version, x.knowledge_uuid, x.knowledge_version,
                       x.outcome_contract, x.source_attribution_uuid, x.source_digest, x.replay_digest,
                       x.evidence_envelope_uuid, x.evidence_envelope_digest, x.engine_version,
                       x.mining_config_digest, x.memory_version, x.memory_state) for x in records}
        if len(identities) > 1: raise PatternPromotionError("MIXED_SOURCE_IDENTITIES")
        return records

    def _record_values(self, record, thresholds, state, reasons, generated_at):
        mapping = dict(source_validation_uuid=record.validation_uuid,
            source_validation_digest=record.validation_digest, source_validator_version=record.validator_version,
            source_validation_policy_version=record.validation_policy_version,
            source_validation_config_digest=record.validation_config_digest,
            source_memory_uuid=record.source_memory_uuid, source_memory_digest=record.source_memory_digest,
            source_pattern_uuid=record.source_pattern_uuid, source_pattern_hash=record.source_pattern_hash,
            source_report_uuid=record.source_report_uuid, source_policy_uuid=record.policy_uuid,
            source_policy_version=record.policy_version, source_attribution_uuid=record.source_attribution_uuid,
            source_digest=record.source_digest, replay_digest=record.replay_digest,
            evidence_envelope_uuid=record.evidence_envelope_uuid,
            evidence_envelope_digest=record.evidence_envelope_digest, knowledge_uuid=record.knowledge_uuid,
            knowledge_version=record.knowledge_version, source_engine_version=record.engine_version,
            mining_config_digest=record.mining_config_digest, outcome_contract=record.outcome_contract,
            memory_version=record.memory_version, memory_state=record.memory_state,
            source_validation_state=record.validation_state, source_validation_reasons=record.validation_reasons,
            source_validation_statistics=record.validation_statistics, source_validated_at=record.validated_at,
            source_validation_thresholds=thresholds, promotion_policy_thresholds=self.policy.thresholds,
            threshold_monotonicity_result="PASSED", promotion_state=state, promotion_reasons=reasons,
            created_at=generated_at, advisory_only=True)
        return dict(promotion_engine_version=self.promotion_engine_version,
                    promotion_policy_uuid=self.policy.policy_uuid,
                    promotion_policy_digest=self.policy.policy_digest,
                    promotion_policy_version=self.policy.promotion_policy_version, **mapping)
