"""Fail-closed PR176 reconstruction, provenance, replay and consistency checks."""
from __future__ import annotations
from dataclasses import replace
from learning.pattern_memory.memory_identity import digest as memory_digest, memory_uuid, report_uuid
from learning.pattern_memory.models import PatternMemoryRecord, PatternMemoryReport
from .exceptions import PatternValidationError
from .statistics import assess


def validate_record(record, config):
    if not isinstance(record, PatternMemoryRecord):
        raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
    try:
        reconstructed = replace(record)
    except (TypeError, ValueError) as exc:
        raise PatternValidationError("BROKEN_PATTERN_MEMORY_RECORD") from exc
    if reconstructed.advisory_only is not True or reconstructed.memory_state != "STORED":
        raise PatternValidationError("UNSUPPORTED_PATTERN_MEMORY_STATE")
    if (memory_digest(reconstructed.memory_identity_payload()) != reconstructed.memory_identity_digest
            or memory_uuid(reconstructed.memory_identity_payload()) != reconstructed.memory_uuid):
        raise PatternValidationError("BROKEN_MEMORY_IDENTITY")
    if memory_digest(reconstructed.digest_payload()) != reconstructed.memory_digest:
        raise PatternValidationError("BROKEN_MEMORY_DIGEST")
    return assess(sample_count=reconstructed.sample_count, support=reconstructed.support,
                  expectancy=reconstructed.expectancy, confidence=reconstructed.confidence,
                  config=config.to_dict())


def validate_report(report):
    if not isinstance(report, PatternMemoryReport):
        raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
    pairs = tuple(sorted((x.memory_uuid, x.memory_digest) for x in report.memory_records))
    repository = dict(report.repository_record_identities)
    if any(repository.get(uuid) != value for uuid, value in pairs):
        raise PatternValidationError("BROKEN_SOURCE_SNAPSHOT")
    if report_uuid(report.identity_payload()) != report.report_uuid:
        raise PatternValidationError("BROKEN_SOURCE_REPLAY")
    identities = {(x.policy_uuid, x.policy_version, x.knowledge_uuid, x.knowledge_version,
                   x.outcome_contract) for x in report.memory_records}
    if len(identities) > 1:
        raise PatternValidationError("MIXED_SOURCE_IDENTITIES")
    if (len(repository) != report.repository_record_count
            or memory_digest([list(x) for x in report.repository_record_identities]) != report.repository_digest):
        raise PatternValidationError("BROKEN_SOURCE_REPOSITORY")
    return report.memory_records
