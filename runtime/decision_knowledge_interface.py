"""Fail-closed Decision read boundary for immutable applicability reports."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re

from runtime.knowledge_applicability import (
    APPLICABILITY_REPORT_CONTRACT_VERSION,
    ApplicableKnowledge,
    ApplicabilityReport,
    semver_major,
)

DECISION_KNOWLEDGE_CONTRACT_VERSION = "1.0.0"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DecisionKnowledgeAccessError(ValueError):
    """Fail-closed error for invalid reports or incompatible access."""


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionKnowledgeAccessError(code)
    return value.strip()


def _strings(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) or not item for item in value):
        raise DecisionKnowledgeAccessError(code)
    return value


@dataclass(frozen=True)
class DecisionKnowledgeRecord:
    knowledge_uuid: str
    semantic_identity: str
    applicability_score: float
    confidence: float
    priority: int
    matching_factors: tuple[str, ...]
    reason_codes: tuple[str, ...]
    snapshot_digest: str
    registry_sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "knowledge_uuid", _identifier(self.knowledge_uuid, "INVALID_KNOWLEDGE_IDENTIFIER"))
        object.__setattr__(self, "semantic_identity", _identifier(self.semantic_identity, "INVALID_SEMANTIC_IDENTITY"))
        if (
            isinstance(self.applicability_score, bool)
            or not isinstance(self.applicability_score, (int, float))
            or not isfinite(self.applicability_score)
            or not 0 <= self.applicability_score <= 1
            or isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
            or not isinstance(self.priority, int)
            or isinstance(self.priority, bool)
            or self.priority < 0
            or not isinstance(self.registry_sequence, int)
            or isinstance(self.registry_sequence, bool)
            or self.registry_sequence < 1
            or not isinstance(self.snapshot_digest, str)
            or not _HEX64.fullmatch(self.snapshot_digest)
        ):
            raise DecisionKnowledgeAccessError("INVALID_DECISION_KNOWLEDGE_RECORD")
        object.__setattr__(self, "applicability_score", float(self.applicability_score))
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "matching_factors", _strings(self.matching_factors, "INVALID_MATCHING_FACTORS"))
        object.__setattr__(self, "reason_codes", _strings(self.reason_codes, "INVALID_REASON_CODES"))


@dataclass(frozen=True)
class DecisionKnowledgeSnapshot:
    contract_version: str
    report_contract_version: str
    report_uuid: str
    report_digest: str
    snapshot_digest: str
    records: tuple[DecisionKnowledgeRecord, ...]

    def __post_init__(self) -> None:
        if semver_major(self.contract_version) != semver_major(DECISION_KNOWLEDGE_CONTRACT_VERSION):
            raise DecisionKnowledgeAccessError("UNSUPPORTED_DECISION_KNOWLEDGE_CONTRACT_VERSION")
        if semver_major(self.report_contract_version) != semver_major(APPLICABILITY_REPORT_CONTRACT_VERSION):
            raise DecisionKnowledgeAccessError("UNSUPPORTED_APPLICABILITY_REPORT_CONTRACT_VERSION")
        _identifier(self.report_uuid, "INVALID_REPORT_UUID")
        if not _HEX64.fullmatch(self.report_digest) or not _HEX64.fullmatch(self.snapshot_digest):
            raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
        if not isinstance(self.records, tuple) or any(not isinstance(item, DecisionKnowledgeRecord) for item in self.records):
            raise DecisionKnowledgeAccessError("INVALID_DECISION_KNOWLEDGE_SNAPSHOT")


class DecisionKnowledgeInterface:
    """Immutable projection. The source ApplicabilityReport is never retained."""

    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: DecisionKnowledgeSnapshot) -> None:
        if not isinstance(snapshot, DecisionKnowledgeSnapshot):
            raise DecisionKnowledgeAccessError("DECISION_KNOWLEDGE_SNAPSHOT_REQUIRED")
        object.__setattr__(self, "_snapshot", snapshot)

    @classmethod
    def load(cls, report: ApplicabilityReport) -> "DecisionKnowledgeInterface":
        return cls(cls._project(report))

    @staticmethod
    def _project(report: object) -> DecisionKnowledgeSnapshot:
        if not isinstance(report, ApplicabilityReport):
            raise DecisionKnowledgeAccessError("MISSING_APPLICABILITY_REPORT")
        try:
            verified = ApplicabilityReport(
                report.snapshot_digest,
                report.context,
                tuple(report.applicable),
                tuple(report.rejected),
                report.confidence,
                report.report_digest,
                report.report_uuid,
                report.report_contract_version,
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT") from exc
        if semver_major(verified.report_contract_version) != semver_major(APPLICABILITY_REPORT_CONTRACT_VERSION):
            raise DecisionKnowledgeAccessError("UNSUPPORTED_APPLICABILITY_REPORT_CONTRACT_VERSION")

        seen_uuid: set[str] = set()
        seen_identity: set[str] = set()
        records: list[DecisionKnowledgeRecord] = []
        for item in verified.applicable:
            if not isinstance(item, ApplicableKnowledge) or item.snapshot_digest != verified.snapshot_digest:
                raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
            if item.knowledge_uuid in seen_uuid or item.semantic_identity in seen_identity:
                raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
            seen_uuid.add(item.knowledge_uuid)
            seen_identity.add(item.semantic_identity)
            records.append(DecisionKnowledgeRecord(
                item.knowledge_uuid,
                item.semantic_identity,
                item.specificity_score,
                item.confidence,
                item.priority,
                tuple(item.matching_factors),
                tuple(item.reason_codes),
                item.snapshot_digest,
                item.registry_sequence,
            ))

        expected = tuple(sorted(records, key=lambda item: (
            -item.priority,
            -item.applicability_score,
            -item.confidence,
            item.semantic_identity,
            item.knowledge_uuid,
        )))
        if tuple(records) != expected:
            raise DecisionKnowledgeAccessError("NON_CANONICAL_APPLICABILITY_ORDER")
        return DecisionKnowledgeSnapshot(
            DECISION_KNOWLEDGE_CONTRACT_VERSION,
            verified.report_contract_version,
            verified.report_uuid,
            verified.report_digest,
            verified.snapshot_digest,
            tuple(records),
        )

    def list_applicable(self) -> tuple[DecisionKnowledgeRecord, ...]:
        return self._snapshot.records

    def lookup(self, knowledge_uuid: str) -> DecisionKnowledgeRecord | None:
        value = _identifier(knowledge_uuid, "INVALID_KNOWLEDGE_IDENTIFIER")
        return next((item for item in self._snapshot.records if item.knowledge_uuid == value), None)

    def resolve(self, semantic_identity: str) -> DecisionKnowledgeRecord | None:
        value = _identifier(semantic_identity, "INVALID_SEMANTIC_IDENTITY")
        return next((item for item in self._snapshot.records if item.semantic_identity == value), None)

    def report_uuid(self) -> str:
        return self._snapshot.report_uuid

    def report_digest(self) -> str:
        return self._snapshot.report_digest

    def snapshot_digest(self) -> str:
        return self._snapshot.snapshot_digest


def load(report: ApplicabilityReport) -> DecisionKnowledgeInterface:
    return DecisionKnowledgeInterface.load(report)


__all__ = [
    "DECISION_KNOWLEDGE_CONTRACT_VERSION",
    "DecisionKnowledgeAccessError",
    "DecisionKnowledgeInterface",
    "DecisionKnowledgeRecord",
    "DecisionKnowledgeSnapshot",
    "load",
]
