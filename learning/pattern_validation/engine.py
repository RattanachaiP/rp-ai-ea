"""PR177 historical validation engine; advisory-only and runtime isolated."""
from __future__ import annotations
from learning.pattern_memory.models import PatternMemoryRecord, PatternMemoryReport
from .exceptions import PatternValidationError
from .models import PatternValidationReport, ValidationRecord
from .repository import PatternValidationRepository
from .validator import validate_record, validate_report


class PatternValidationEngine:
    def __init__(self, repository=None): self.repository = repository or PatternValidationRepository()
    def validate(self, source):
        if type(source) not in (PatternMemoryReport, PatternMemoryRecord):
            raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
        records = validate_report(source) if isinstance(source, PatternMemoryReport) else (source,)
        generated_at = source.generated_at if isinstance(source, PatternMemoryReport) else source.created_at
        output = []
        existing = {x.validation_uuid: x for x in self.repository.records()}
        for record in records:
            state, reasons, statistics = validate_record(record)
            item = ValidationRecord.create(memory_uuid=record.memory_uuid, memory_digest=record.memory_digest,
                pattern_uuid=record.pattern_uuid, policy_uuid=record.policy_uuid, knowledge_uuid=record.knowledge_uuid,
                validation_state=state, validation_reasons=reasons, validation_statistics=statistics,
                validated_at=generated_at, advisory_only=True)
            prior = existing.get(item.validation_uuid)
            if prior and prior.validation_digest != item.validation_digest: raise PatternValidationError("DUPLICATE_VALIDATION_HISTORY")
            self.repository.save(item); output.append(item)
        return PatternValidationReport.create(output, self.repository.digest(), generated_at)

    run = validate
