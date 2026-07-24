"""Read-only Decision access boundary for immutable applicability reports.

This module deliberately exposes a small DTO instead of ``ApplicableKnowledge``.
It is the sole Runtime-facing representation a Decision Engine may consume.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Any
from uuid import UUID

from runtime.knowledge_applicability import ApplicableKnowledge, ApplicabilityReport


DECISION_KNOWLEDGE_CONTRACT_VERSION = "1.0.0"
APPLICABILITY_REPORT_VERSION = "1.0.0"  # PR159 reports predate an explicit version field.
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DecisionKnowledgeAccessError(ValueError):
    """Fail-closed error raised for invalid reports or incompatible queries."""


def _major(version: object) -> int | None:
    match = _SEMVER.fullmatch(version) if isinstance(version, str) else None
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class RuntimeQuery:
    """Optional, immutable selector supplied by the Decision Engine."""

    report_uuid: str | None = None
    contract_version: str = DECISION_KNOWLEDGE_CONTRACT_VERSION
    knowledge_uuid: str | None = None
    semantic_identity: str | None = None

    def __post_init__(self) -> None:
        if _major(self.contract_version) != _major(DECISION_KNOWLEDGE_CONTRACT_VERSION):
            raise DecisionKnowledgeAccessError("UNSUPPORTED_DECISION_KNOWLEDGE_CONTRACT_VERSION")
        if self.report_uuid is not None:
            _validate_uuid(self.report_uuid, "INVALID_REPORT_UUID")
        for value, code in ((self.knowledge_uuid, "INVALID_KNOWLEDGE_UUID"),
                            (self.semantic_identity, "INVALID_SEMANTIC_IDENTITY")):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise DecisionKnowledgeAccessError(code)


@dataclass(frozen=True)
class DecisionKnowledgeRecord:
    """The complete and intentionally limited Decision read contract."""

    knowledge_uuid: str
    semantic_identity: str
    applicability_score: float
    confidence: float
    priority: int
    matching_factors: tuple[str, ...]
    reason_codes: tuple[str, ...]
    snapshot_digest: str
    registry_sequence: int


def _validate_uuid(value: object, code: str) -> None:
    if not isinstance(value, str):
        raise DecisionKnowledgeAccessError(code)
    try:
        UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise DecisionKnowledgeAccessError(code) from exc


class DecisionKnowledgeInterface:
    """Immutable applicability-report reader; it never evaluates or modifies knowledge.

    ``load`` creates a new interface rather than changing an existing instance.  This
    makes report selection explicit and prevents mutable report/cache state.
    """

    def __init__(self, report: ApplicabilityReport) -> None:
        self._report = self._validate_report(report)

    @classmethod
    def load(cls, report: ApplicabilityReport) -> "DecisionKnowledgeInterface":
        return cls(report)

    @staticmethod
    def _validate_report(report: object) -> ApplicabilityReport:
        if not isinstance(report, ApplicabilityReport):
            raise DecisionKnowledgeAccessError("MISSING_APPLICABILITY_REPORT")
        report_version = getattr(report, "report_version", APPLICABILITY_REPORT_VERSION)
        if _major(report_version) != _major(APPLICABILITY_REPORT_VERSION):
            raise DecisionKnowledgeAccessError("UNKNOWN_APPLICABILITY_REPORT_VERSION")
        _validate_uuid(report.report_uuid, "INVALID_REPORT_UUID")
        if not isinstance(report.report_digest, str) or not _HEX64.fullmatch(report.report_digest):
            raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
        try:
            # Reconstructing validates the canonical digest and deterministic UUID.
            verified = ApplicabilityReport(report.snapshot_digest, report.context, tuple(report.applicable),
                                           tuple(report.rejected), report.confidence,
                                           report.report_digest, report.report_uuid)
        except (TypeError, ValueError, AttributeError) as exc:
            raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT") from exc
        seen_uuid, seen_identity = set(), set()
        for item in verified.applicable:
            if not isinstance(item, ApplicableKnowledge):
                raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
            if item.knowledge_uuid in seen_uuid or item.semantic_identity in seen_identity:
                raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
            if not (isfinite(item.specificity_score) and isfinite(item.confidence)):
                raise DecisionKnowledgeAccessError("CORRUPTED_APPLICABILITY_REPORT")
            seen_uuid.add(item.knowledge_uuid)
            seen_identity.add(item.semantic_identity)
        return verified

    def _query(self, query: RuntimeQuery | None) -> RuntimeQuery:
        if query is None:
            return RuntimeQuery()
        if not isinstance(query, RuntimeQuery):
            raise DecisionKnowledgeAccessError("RUNTIME_QUERY_REQUIRED")
        if query.report_uuid is not None and query.report_uuid != self._report.report_uuid:
            raise DecisionKnowledgeAccessError("MISSING_APPLICABILITY_REPORT")
        return query

    @staticmethod
    def _record(item: ApplicableKnowledge) -> DecisionKnowledgeRecord:
        return DecisionKnowledgeRecord(item.knowledge_uuid, item.semantic_identity, item.specificity_score,
                                       item.confidence, item.priority, tuple(item.matching_factors),
                                       tuple(item.reason_codes), item.snapshot_digest, item.registry_sequence)

    def get_applicable(self, query: RuntimeQuery | None = None) -> tuple[DecisionKnowledgeRecord, ...]:
        query = self._query(query)
        records = tuple(self._record(item) for item in self._report.applicable)
        if query.knowledge_uuid is not None:
            records = tuple(item for item in records if item.knowledge_uuid == query.knowledge_uuid)
        if query.semantic_identity is not None:
            records = tuple(item for item in records if item.semantic_identity == query.semantic_identity)
        return records

    def list_applicable(self, query: RuntimeQuery | None = None) -> tuple[DecisionKnowledgeRecord, ...]:
        return self.get_applicable(query)

    def lookup(self, knowledge_uuid: str, query: RuntimeQuery | None = None) -> DecisionKnowledgeRecord | None:
        _validate_uuid(knowledge_uuid, "INVALID_KNOWLEDGE_UUID")
        query = self._query(query)
        if query.knowledge_uuid is not None and query.knowledge_uuid != knowledge_uuid:
            return None
        return next((item for item in self.get_applicable(query) if item.knowledge_uuid == knowledge_uuid), None)

    def resolve(self, semantic_identity: str, query: RuntimeQuery | None = None) -> DecisionKnowledgeRecord | None:
        if not isinstance(semantic_identity, str) or not semantic_identity.strip():
            raise DecisionKnowledgeAccessError("INVALID_SEMANTIC_IDENTITY")
        query = self._query(query)
        if query.semantic_identity is not None and query.semantic_identity != semantic_identity:
            return None
        return self.get_by_semantic_identity(semantic_identity, query)

    def get_by_semantic_identity(self, semantic_identity: str, query: RuntimeQuery | None = None) -> DecisionKnowledgeRecord | None:
        return next((item for item in self.get_applicable(query) if item.semantic_identity == semantic_identity), None)

    def report_digest(self, query: RuntimeQuery | None = None) -> str:
        self._query(query)
        return self._report.report_digest

    def snapshot_digest(self, query: RuntimeQuery | None = None) -> str:
        self._query(query)
        return self._report.snapshot_digest


def load(report: ApplicabilityReport) -> DecisionKnowledgeInterface:
    """Load and validate an immutable report into a fresh DKI reader."""
    return DecisionKnowledgeInterface.load(report)


__all__ = [
    "APPLICABILITY_REPORT_VERSION", "DECISION_KNOWLEDGE_CONTRACT_VERSION",
    "DecisionKnowledgeAccessError", "DecisionKnowledgeInterface", "DecisionKnowledgeRecord",
    "RuntimeQuery", "load",
]
