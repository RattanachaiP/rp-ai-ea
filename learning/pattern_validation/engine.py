"""PR177 offline historical validation with no operational authority."""
from __future__ import annotations
from learning.pattern_memory.memory_identity import digest as memory_digest
from learning.pattern_memory.models import PatternMemoryRecord, PatternMemoryReport
from .exceptions import PatternValidationError
from .models import (PatternValidationReport, PatternValidationSnapshot, ValidationConfig,
                     ValidationRecord)
from .repository import PatternValidationRepository
from .validator import validate_record, validate_report


class PatternValidationEngine:
    validator_version = "PR177.2.0"
    validation_policy_version = "PR177-POLICY.1.0"

    def __init__(self, repository=None, config=None, *, validator_version=None,
                 validation_policy_version=None):
        self.repository = repository or PatternValidationRepository()
        self.config = config or ValidationConfig()
        if not isinstance(self.config, ValidationConfig):
            raise PatternValidationError("INVALID_VALIDATION_CONFIG")
        self.validator_version = validator_version or type(self).validator_version
        self.validation_policy_version = validation_policy_version or type(self).validation_policy_version
        if not all(isinstance(x, str) and x for x in
                   (self.validator_version, self.validation_policy_version)):
            raise PatternValidationError("INVALID_VALIDATION_POLICY_IDENTITY")

    def validate(self, source):
        if type(source) not in (PatternMemoryReport, PatternMemoryRecord):
            raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
        if isinstance(source, PatternMemoryReport):
            records = validate_report(source)
            generated_at = source.generated_at
            source_fields = {"source_artifact_type": "PATTERN_MEMORY_REPORT",
                "source_pattern_memory_report_uuid": source.report_uuid,
                "source_pattern_memory_report_digest": memory_digest(source.to_dict()),
                "source_snapshot_uuid": source.snapshot_uuid, "source_snapshot_digest": source.snapshot_digest,
                "source_memory_uuid": None, "source_memory_digest": None}
        else:
            records = (source,); generated_at = source.created_at
            source_fields = {"source_artifact_type": "PATTERN_MEMORY_RECORD",
                "source_pattern_memory_report_uuid": None, "source_pattern_memory_report_digest": None,
                "source_snapshot_uuid": None, "source_snapshot_digest": None,
                "source_memory_uuid": source.memory_uuid, "source_memory_digest": source.memory_digest}

        existing = {x.validation_uuid: x for x in self.repository.records()}
        previous_snapshot = self.repository.latest_snapshot()
        if previous_snapshot and previous_snapshot.record_identities != self.repository.identities():
            raise PatternValidationError("VALIDATION_REPOSITORY_SNAPSHOT_MISMATCH")
        output, new_count, duplicate_count = [], 0, 0
        for record in records:
            state, reasons, statistics = validate_record(record, self.config)
            item = ValidationRecord.create(**self._record_values(record, state, reasons, statistics, generated_at))
            prior = existing.get(item.validation_uuid)
            if prior:
                if prior.validation_digest != item.validation_digest:
                    raise PatternValidationError("DUPLICATE_VALIDATION_HISTORY")
                duplicate_count += 1
            else:
                self.repository.save(item); existing[item.validation_uuid] = item; new_count += 1
            output.append(item)

        identities = self.repository.identities()
        if previous_snapshot and previous_snapshot.record_identities == identities:
            snapshot = previous_snapshot
        else:
            snapshot = PatternValidationSnapshot.create(self.validator_version, identities,
                                                        previous_snapshot, generated_at)
            self.repository.save_snapshot(snapshot)
        counts = {state: sum(x.validation_state == state for x in output)
                  for state in ("STATISTICALLY_CONSISTENT", "INVALID", "INSUFFICIENT_EVIDENCE")}
        return PatternValidationReport.create(validator_version=self.validator_version,
            validation_policy_version=self.validation_policy_version,
            validation_config_digest=self.config.config_digest, **source_fields,
            validation_records=tuple(output), processed_record_count=len(output),
            new_validation_count=new_count, duplicate_validation_count=duplicate_count,
            statistically_consistent_count=counts["STATISTICALLY_CONSISTENT"],
            invalid_count=counts["INVALID"], insufficient_count=counts["INSUFFICIENT_EVIDENCE"],
            repository_digest=self.repository.digest(), snapshot_uuid=snapshot.snapshot_uuid,
            snapshot_digest=snapshot.snapshot_digest, generated_at=generated_at, advisory_only=True)

    run = validate

    def _record_values(self, record, state, reasons, statistics, generated_at):
        return {"validator_version": self.validator_version,
            "validation_policy_version": self.validation_policy_version,
            "validation_config_digest": self.config.config_digest,
            "source_memory_uuid": record.memory_uuid, "source_memory_digest": record.memory_digest,
            "source_pattern_uuid": record.pattern_uuid, "source_pattern_hash": record.pattern_hash,
            "source_report_uuid": record.report_uuid, "policy_uuid": record.policy_uuid,
            "policy_version": record.policy_version, "source_attribution_uuid": record.source_attribution_uuid,
            "source_digest": record.source_digest, "replay_digest": record.replay_digest,
            "evidence_envelope_uuid": record.evidence_envelope_uuid,
            "evidence_envelope_digest": record.evidence_envelope_digest,
            "knowledge_uuid": record.knowledge_uuid, "knowledge_version": record.knowledge_version,
            "engine_version": record.engine_version, "mining_config_digest": record.mining_config_digest,
            "outcome_contract": record.outcome_contract, "memory_version": record.memory_version,
            "memory_state": record.memory_state, "validation_state": state,
            "validation_reasons": reasons, "validation_statistics": statistics,
            "validated_at": generated_at, "advisory_only": True}
