"""Fail-closed integrity and statistical validation."""
from __future__ import annotations
from learning.pattern_memory.memory_identity import digest, memory_uuid, report_uuid
from learning.pattern_memory.models import PatternMemoryRecord, PatternMemoryReport
from .exceptions import PatternValidationError
from .statistics import assess


def validate_record(record):
    if not isinstance(record, PatternMemoryRecord): raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
    if digest(record.memory_identity_payload()) != record.memory_identity_digest or memory_uuid(record.memory_identity_payload()) != record.memory_uuid:
        raise PatternValidationError("BROKEN_MEMORY_IDENTITY")
    if digest(record.digest_payload()) != record.memory_digest: raise PatternValidationError("BROKEN_MEMORY_DIGEST")
    return assess(sample_count=record.sample_count, support=record.support,
                  expectancy=record.expectancy, confidence=record.confidence)


def validate_report(report):
    if not isinstance(report, PatternMemoryReport): raise PatternValidationError("INVALID_PATTERN_MEMORY_INPUT")
    pairs = tuple(sorted((x.memory_uuid, x.memory_digest) for x in report.memory_records))
    repository = dict(report.repository_record_identities)
    if any(repository.get(uuid) != value for uuid, value in pairs): raise PatternValidationError("BROKEN_SNAPSHOT_CHAIN")
    if report_uuid(report.identity_payload()) != report.report_uuid: raise PatternValidationError("BROKEN_REPLAY")
    identities = {(x.policy_uuid, x.knowledge_uuid, x.outcome_contract) for x in report.memory_records}
    if len(identities) > 1: raise PatternValidationError("MIXED_IDENTITIES")
    if len(repository) != report.repository_record_count or digest([list(x) for x in report.repository_record_identities]) != report.repository_digest:
        raise PatternValidationError("BROKEN_REPOSITORY_INTEGRITY")
    return report.memory_records
