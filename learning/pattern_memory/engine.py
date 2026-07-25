"""PR176 offline historical Pattern Memory; no learning or runtime authority."""
from __future__ import annotations
from dataclasses import replace
from learning.pattern_mining import PatternMiningReport
from .exceptions import PatternMemoryError
from .memory_identity import digest, report_uuid
from .memory_index import PatternMemoryIndex
from .models import PatternMemoryRecord, PatternMemoryReport, PatternMemorySnapshot
from .repository import PatternMemoryRepository


class PatternMemoryEngine:
    """Consumes only immutable PR175 reports and stores governed history."""
    memory_version = "PR176.2.0"

    def __init__(self, repository: PatternMemoryRepository | None = None):
        self.repository = repository or PatternMemoryRepository()

    def create(self, report: PatternMiningReport) -> PatternMemoryReport:
        if not isinstance(report, PatternMiningReport):
            raise PatternMemoryError("INVALID_PATTERN_MINING_REPORT")
        self._validate_report(report)
        source_digest = digest(report.to_dict())
        existing = self.repository.records()
        previous_snapshot = self.repository.latest_snapshot()
        existing_pairs = tuple((item.memory_uuid, item.memory_digest)
                               for item in sorted(existing, key=lambda value: value.memory_uuid))
        if previous_snapshot and previous_snapshot.record_identities != existing_pairs:
            raise PatternMemoryError("REPOSITORY_SNAPSHOT_MISMATCH")
        existing_by_uuid = {record.memory_uuid: record for record in existing}
        incoming_by_uuid: dict[str, PatternMemoryRecord] = {}
        new_records: list[PatternMemoryRecord] = []
        duplicates = 0
        for pattern in report.candidate_patterns:
            record = PatternMemoryRecord.create(
                pattern_uuid=pattern.pattern_uuid, pattern_hash=pattern.pattern_hash, report_uuid=report.report_uuid,
                policy_uuid=report.policy_uuid, policy_version=pattern.policy_version,
                source_attribution_uuid=report.source_attribution_uuid, source_digest=report.source_digest,
                replay_digest=report.replay_digest, evidence_envelope_uuid=report.evidence_envelope_uuid,
                evidence_envelope_digest=report.evidence_envelope_digest, knowledge_uuid=pattern.knowledge_uuid,
                knowledge_version=pattern.knowledge_version, engine_version=report.engine_version,
                mining_config_digest=report.mining_config_digest, outcome_contract=pattern.outcome_contract,
                feature_signature=pattern.feature_signature, market_context=pattern.market_context,
                entry_context=pattern.entry_context, exit_context=pattern.exit_context, risk_context=pattern.risk_context,
                sample_count=pattern.sample_count, support=pattern.support, expectancy=pattern.expectancy,
                confidence=pattern.confidence, memory_version=self.memory_version, created_at=report.generated_at,
                advisory_only=True, memory_state="STORED")
            prior = incoming_by_uuid.get(record.memory_uuid) or existing_by_uuid.get(record.memory_uuid)
            if prior is not None:
                if prior.memory_digest != record.memory_digest:
                    raise PatternMemoryError("MEMORY_CONFLICT")
                duplicates += 1
                continue
            incoming_by_uuid[record.memory_uuid] = record
            new_records.append(record)
        for record in new_records:
            self.repository.save(record)
        snapshot_records = tuple(sorted((*existing, *new_records), key=lambda item: item.memory_uuid))
        pairs = tuple((item.memory_uuid, item.memory_digest) for item in snapshot_records)
        repository_digest = digest([list(item) for item in pairs])
        if previous_snapshot and previous_snapshot.record_identities == pairs:
            snapshot = previous_snapshot
        else:
            snapshot = PatternMemorySnapshot.create(memory_version=self.memory_version, record_identities=pairs,
                                                    previous=previous_snapshot, generated_at=report.generated_at)
            self.repository.save_snapshot(snapshot)
        values = {"source_pattern_mining_report_uuid": report.report_uuid,
                  "source_pattern_mining_report_digest": source_digest, "memory_version": self.memory_version,
                  "memory_records": tuple(new_records), "memory_count": len(new_records),
                  "duplicate_count": duplicates, "rejected_count": 0, "repository_digest": repository_digest,
                  "repository_record_count": len(pairs), "repository_record_identities": pairs,
                  "snapshot_uuid": snapshot.snapshot_uuid, "snapshot_digest": snapshot.snapshot_digest,
                  "generated_at": report.generated_at, "advisory_only": True}
        identity = {**values, "memory_records": [item.to_dict() for item in new_records],
                    "repository_record_identities": [list(item) for item in pairs]}
        return PatternMemoryReport(report_uuid(identity), **values)

    remember = create
    build = create

    def index(self) -> PatternMemoryIndex:
        return PatternMemoryIndex.build(self.repository.records())

    def _validate_report(self, report: PatternMiningReport) -> None:
        patterns = report.candidate_patterns
        if report.advisory_only is not True or not patterns:
            raise PatternMemoryError("INVALID_PATTERN_MINING_REPORT")
        policy_versions = {item.policy_version for item in patterns}
        knowledge = {(item.knowledge_uuid, item.knowledge_version) for item in patterns}
        contracts = {tuple(item.outcome_contract) for item in patterns}
        if len(policy_versions) != 1:
            raise PatternMemoryError("MIXED_POLICY_VERSION")
        if len(knowledge) != 1:
            raise PatternMemoryError("MIXED_KNOWLEDGE_IDENTITY")
        if len(contracts) != 1:
            raise PatternMemoryError("MIXED_OUTCOME_CONTRACT")
        for pattern in patterns:
            expected = (report.policy_uuid, report.source_attribution_uuid, report.source_digest,
                        report.replay_digest, report.engine_version)
            actual = (pattern.policy_uuid, pattern.source_attribution_uuid, pattern.source_digest,
                      pattern.replay_digest, pattern.engine_version)
            if actual != expected:
                raise PatternMemoryError("BROKEN_PATTERN_PROVENANCE")
        try:
            # Defense in depth after PR176's explicit consumption contract.
            replace(report)
        except (TypeError, ValueError) as exc:
            raise PatternMemoryError("BROKEN_REPORT_IDENTITY") from exc
