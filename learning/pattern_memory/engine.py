"""PR176 offline Pattern Memory orchestration; no learning or runtime authority."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from learning.common.immutable import thaw
from learning.pattern_mining import PatternMiningReport

from .exceptions import PatternMemoryError
from .memory_identity import digest, memory_uuid, report_uuid
from .memory_index import PatternMemoryIndex
from .models import PatternMemoryRecord, PatternMemoryReport
from .repository import PatternMemoryRepository


class PatternMemoryEngine:
    """Converts only immutable mining reports into immutable historical memory."""
    memory_version = "PR176.1.0"

    def __init__(self, repository: PatternMemoryRepository | None = None):
        self.repository = repository or PatternMemoryRepository()

    def create(self, report: PatternMiningReport) -> PatternMemoryReport:
        if not isinstance(report, PatternMiningReport):
            raise PatternMemoryError("INVALID_PATTERN_MINING_REPORT")
        self._validate_report(report)
        existing = self.repository.records()
        by_pattern = {record.pattern_uuid: record for record in existing}
        new_records: list[PatternMemoryRecord] = []
        duplicates = 0
        seen: dict[str, PatternMemoryRecord] = {}
        for pattern in report.candidate_patterns:
            record = self._record(report, pattern)
            prior = seen.get(record.pattern_uuid) or by_pattern.get(record.pattern_uuid)
            if prior:
                if prior.memory_digest != record.memory_digest:
                    raise PatternMemoryError("MEMORY_CONFLICT")
                duplicates += 1
                continue
            seen[record.pattern_uuid] = record
            new_records.append(record)
        for record in new_records:
            self.repository.save(record)
        snapshot = tuple(sorted((*existing, *new_records), key=lambda item: item.memory_uuid))
        repository_digest = digest([item.to_dict() for item in snapshot])
        identity = {"memory_records": [x.to_dict() for x in new_records], "memory_count": len(new_records),
                    "duplicate_count": duplicates, "rejected_count": 0,
                    "repository_digest": repository_digest, "generated_at": report.generated_at,
                    "advisory_only": True}
        return PatternMemoryReport(report_uuid(identity), tuple(new_records), len(new_records), duplicates, 0,
                                   repository_digest, report.generated_at, True)

    remember = create
    build = create

    def index(self) -> PatternMemoryIndex:
        return PatternMemoryIndex.build(self.repository.records())

    def _validate_report(self, report: PatternMiningReport) -> None:
        try:
            # Re-run PR175's content-addressed model boundary in case a frozen
            # artifact was tampered with through low-level Python mutation.
            replace(report)
        except (TypeError, ValueError) as exc:
            raise PatternMemoryError("BROKEN_REPORT_IDENTITY") from exc
        if report.advisory_only is not True or not report.candidate_patterns:
            raise PatternMemoryError("INVALID_PATTERN_MINING_REPORT")
        knowledge = {(x.knowledge_uuid, x.knowledge_version) for x in report.candidate_patterns}
        if len(knowledge) != 1:
            raise PatternMemoryError("MIXED_KNOWLEDGE_IDENTITY")
        for pattern in report.candidate_patterns:
            if (pattern.policy_uuid != report.policy_uuid
                    or pattern.source_attribution_uuid != report.source_attribution_uuid
                    or pattern.engine_version != report.engine_version):
                raise PatternMemoryError("BROKEN_PATTERN_PROVENANCE")

    def _record(self, report: PatternMiningReport, pattern: Any) -> PatternMemoryRecord:
        identity = {"pattern_uuid": pattern.pattern_uuid, "pattern_hash": pattern.pattern_hash,
                    "policy_uuid": report.policy_uuid, "evidence_envelope_uuid": report.evidence_envelope_uuid,
                    "knowledge_uuid": pattern.knowledge_uuid, "mining_config_digest": report.mining_config_digest,
                    "memory_version": self.memory_version}
        values = {"pattern_uuid": pattern.pattern_uuid, "pattern_hash": pattern.pattern_hash,
                  "report_uuid": report.report_uuid, "policy_uuid": report.policy_uuid,
                  "source_attribution_uuid": report.source_attribution_uuid,
                  "evidence_envelope_uuid": report.evidence_envelope_uuid, "knowledge_uuid": pattern.knowledge_uuid,
                  "knowledge_version": pattern.knowledge_version, "engine_version": pattern.engine_version,
                  "feature_signature": pattern.feature_signature, "market_context": thaw(pattern.market_context),
                  "entry_context": thaw(pattern.entry_context), "exit_context": thaw(pattern.exit_context),
                  "risk_context": thaw(pattern.risk_context), "sample_count": pattern.sample_count,
                  "support": pattern.support, "expectancy": pattern.expectancy, "confidence": pattern.confidence,
                  "memory_version": self.memory_version, "created_at": report.generated_at,
                  "advisory_only": True, "memory_state": "ACTIVE"}
        return PatternMemoryRecord(memory_uuid(identity), digest(values), **values)
