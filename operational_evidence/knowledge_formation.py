"""PR207 passive qualification of immutable operational patterns.

Knowledge formation is deliberately evidence-only.  This module has no
dependency on Runtime, Strategy, governance, or broker components.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Iterable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from operational_evidence.outcome_attribution import OutcomeAttribution
from operational_evidence.pattern_discovery import (
    Pattern, PatternDiscoveryConfig, PatternDiscoveryEngine, PatternDiscoveryError,
)
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import LiveOutcomeRecord


KNOWLEDGE_VERSION = "PR207-CANDIDATE-KNOWLEDGE.2"
QUALIFICATION_POLICY_VERSION = "PR207-QUALIFICATION-POLICY.1"
QUALIFICATION_STATUSES = frozenset({"CANDIDATE", "THRESHOLD_ELIGIBLE", "REJECTED"})
_KNOWN_PATTERN_TYPES = frozenset({
    "WINNING_TRADE_CHARACTERISTICS", "LOSING_TRADE_CHARACTERISTICS",
    "ENTRY_TIMING_CLUSTER", "EXIT_TIMING_CLUSTER", "STOP_LOSS_DISTRIBUTION",
    "TAKE_PROFIT_DISTRIBUTION", "TRADE_DURATION_DISTRIBUTION",
    "LATENCY_DISTRIBUTION", "MANUAL_INTERVENTION_FREQUENCY",
    "REPLAY_CONSISTENCY",
})


class KnowledgeFormationError(ValueError):
    """A fail-closed validation, qualification, or persistence failure."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise KnowledgeFormationError("KNOWLEDGE_SERIALIZATION_FAILURE") from exc


def _valid_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True, slots=True)
class KnowledgeQualificationPolicy:
    """Explicit deterministic thresholds; no score or prediction is derived."""

    qualification_policy_version: str = QUALIFICATION_POLICY_VERSION
    minimum_qualified_sample_count: int = 10
    minimum_configured_confidence_level: float = 0.95
    minimum_candidate_confidence_level: float = 0.80

    def __post_init__(self) -> None:
        if self.qualification_policy_version != QUALIFICATION_POLICY_VERSION:
            raise KnowledgeFormationError("INVALID_QUALIFICATION_POLICY_VERSION")
        if (not isinstance(self.minimum_qualified_sample_count, int)
                or isinstance(self.minimum_qualified_sample_count, bool)
                or self.minimum_qualified_sample_count < 2):
            raise KnowledgeFormationError("INVALID_QUALIFICATION_SAMPLE_THRESHOLD")
        if (not isinstance(self.minimum_configured_confidence_level, (int, float))
                or isinstance(self.minimum_configured_confidence_level, bool)
                or not 0.5 < self.minimum_configured_confidence_level < 1):
            raise KnowledgeFormationError("INVALID_QUALIFICATION_CONFIDENCE_THRESHOLD")
        if (not isinstance(self.minimum_candidate_confidence_level, (int, float))
                or isinstance(self.minimum_candidate_confidence_level, bool)
                or not 0.5 < self.minimum_candidate_confidence_level
                <= self.minimum_configured_confidence_level):
            raise KnowledgeFormationError("INVALID_CANDIDATE_CONFIDENCE_THRESHOLD")


@dataclass(frozen=True, slots=True)
class EvidenceReferences:
    pattern_uuid: str
    attribution_uuids: tuple[str, ...]
    completed_trade_event_uuids: tuple[str, ...]
    live_outcome_record_uuids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "pattern_uuid": self.pattern_uuid,
            "attribution_uuids": list(self.attribution_uuids),
            "completed_trade_event_uuids": list(self.completed_trade_event_uuids),
            "live_outcome_record_uuids": list(self.live_outcome_record_uuids),
        }


@dataclass(frozen=True, slots=True)
class CandidateKnowledge:
    knowledge_uuid: str
    parent_pattern_uuid: str
    qualification_status: str
    qualification_rationale: tuple[str, ...]
    qualification_policy_version: str
    minimum_qualified_sample_count: int
    minimum_configured_confidence_level: float
    minimum_candidate_confidence_level: float
    evidence_references: EvidenceReferences
    qualification_timestamp: str
    replay_identity: str
    sha256_digest: str
    contract_version: str = KNOWLEDGE_VERSION
    passive_evidence_only: bool = True

    def __post_init__(self) -> None:
        if self.contract_version != KNOWLEDGE_VERSION or not self.passive_evidence_only:
            raise KnowledgeFormationError("INVALID_KNOWLEDGE_CONTRACT")
        if not _valid_uuid(self.knowledge_uuid) or not _valid_uuid(self.parent_pattern_uuid):
            raise KnowledgeFormationError("INVALID_KNOWLEDGE_UUID")
        if not _valid_uuid(self.replay_identity):
            raise KnowledgeFormationError("INVALID_REPLAY_IDENTITY")
        if self.qualification_status not in QUALIFICATION_STATUSES:
            raise KnowledgeFormationError("INVALID_QUALIFICATION_STATUS")
        KnowledgeQualificationPolicy(
            qualification_policy_version=self.qualification_policy_version,
            minimum_qualified_sample_count=self.minimum_qualified_sample_count,
            minimum_configured_confidence_level=self.minimum_configured_confidence_level,
            minimum_candidate_confidence_level=self.minimum_candidate_confidence_level,
        )
        if (not self.qualification_rationale
                or tuple(sorted(set(self.qualification_rationale))) != self.qualification_rationale):
            raise KnowledgeFormationError("INVALID_QUALIFICATION_RATIONALE")
        refs = self.evidence_references
        if (refs.pattern_uuid != self.parent_pattern_uuid
                or not refs.attribution_uuids
                or any(tuple(sorted(set(values))) != values for values in (
                    refs.attribution_uuids, refs.completed_trade_event_uuids,
                    refs.live_outcome_record_uuids))
                or not all(_valid_uuid(item) for values in (
                    refs.attribution_uuids, refs.completed_trade_event_uuids,
                    refs.live_outcome_record_uuids) for item in values)):
            raise KnowledgeFormationError("INVALID_EVIDENCE_REFERENCES")
        expected_uuid = str(uuid5(NAMESPACE_URL, "pr207-candidate-knowledge:" + sha256(
            _canonical(self._identity_body())).hexdigest()))
        if self.knowledge_uuid != expected_uuid:
            raise KnowledgeFormationError("KNOWLEDGE_UUID_MISMATCH")
        if self.sha256_digest != sha256(_canonical(self._body())).hexdigest():
            raise KnowledgeFormationError("KNOWLEDGE_DIGEST_MISMATCH")

    def _identity_body(self) -> dict[str, object]:
        return {
            "parent_pattern_uuid": self.parent_pattern_uuid,
            "qualification_status": self.qualification_status,
            "qualification_rationale": list(self.qualification_rationale),
            "qualification_policy_version": self.qualification_policy_version,
            "minimum_qualified_sample_count": self.minimum_qualified_sample_count,
            "minimum_configured_confidence_level": self.minimum_configured_confidence_level,
            "minimum_candidate_confidence_level": self.minimum_candidate_confidence_level,
            "evidence_references": self.evidence_references.to_dict(),
            "qualification_timestamp": self.qualification_timestamp,
            "replay_identity": self.replay_identity,
            "contract_version": self.contract_version,
            "passive_evidence_only": self.passive_evidence_only,
        }

    def _body(self) -> dict[str, object]:
        return {"knowledge_uuid": self.knowledge_uuid, **self._identity_body()}

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "sha256_digest": self.sha256_digest}

    def canonical_bytes(self) -> bytes:
        """Return the complete canonical serialization stored by repositories."""
        return _canonical(self.to_dict())


class KnowledgeFormationEngine:
    """Validate exact source lineage and apply declared qualification rules."""

    def __init__(self, policy: KnowledgeQualificationPolicy | None = None) -> None:
        self.policy = policy or KnowledgeQualificationPolicy()

    def form(self, pattern: Pattern, attributions: Iterable[OutcomeAttribution],
             completed_events: Iterable[CompletedTradeEvent],
             live_outcomes: Iterable[LiveOutcomeRecord]) -> CandidateKnowledge:
        if type(pattern) is not Pattern:
            raise KnowledgeFormationError("PATTERN_REQUIRED")
        try:
            pattern.__post_init__()
        except (PatternDiscoveryError, TypeError, ValueError) as exc:
            raise KnowledgeFormationError("PATTERN_INTEGRITY_FAILURE") from exc

        attrs, events, outcomes = tuple(attributions), tuple(completed_events), tuple(live_outcomes)
        if (not attrs or len({item.attribution_uuid for item in attrs}) != len(attrs)
                or len({item.event_uuid for item in events}) != len(events)
                or len({item.record_uuid for item in outcomes}) != len(outcomes)):
            raise KnowledgeFormationError("DUPLICATE_OR_EMPTY_SOURCE_EVIDENCE")
        if tuple(sorted(item.attribution_uuid for item in attrs)) != pattern.source_attribution_uuids:
            raise KnowledgeFormationError("SOURCE_COMPLETENESS_FAILURE")
        expected_events = tuple(sorted(item.parent_completed_trade_event_uuid for item in attrs))
        expected_outcomes = tuple(sorted(item.source_live_outcome_record_uuid for item in attrs))
        if (tuple(sorted(item.event_uuid for item in events)) != expected_events
                or tuple(sorted(item.record_uuid for item in outcomes)) != expected_outcomes):
            raise KnowledgeFormationError("SOURCE_COMPLETENESS_FAILURE")
        if any(item.replay_identity != pattern.replay_identity for item in attrs):
            raise KnowledgeFormationError("REPLAY_IDENTITY_CHAIN_FAILURE")
        try:
            recreated = PatternDiscoveryEngine(PatternDiscoveryConfig(
                minimum_sample_count=2,
                confidence_level=pattern.configured_confidence_level,
            )).discover(attrs, events, outcomes)
        except (PatternDiscoveryError, TypeError, ValueError) as exc:
            raise KnowledgeFormationError("SOURCE_INTEGRITY_FAILURE") from exc
        if pattern not in recreated:
            raise KnowledgeFormationError("PATTERN_SOURCE_LINEAGE_FAILURE")
        status, reasons = self._qualify(pattern)
        references = EvidenceReferences(
            pattern.pattern_uuid,
            tuple(sorted(item.attribution_uuid for item in attrs)),
            tuple(sorted(item.event_uuid for item in events)),
            tuple(sorted(item.record_uuid for item in outcomes)),
        )
        values = {
            "parent_pattern_uuid": pattern.pattern_uuid,
            "qualification_status": status,
            "qualification_rationale": tuple(sorted(reasons)),
            "qualification_policy_version": self.policy.qualification_policy_version,
            "minimum_qualified_sample_count": self.policy.minimum_qualified_sample_count,
            "minimum_configured_confidence_level": self.policy.minimum_configured_confidence_level,
            "minimum_candidate_confidence_level": self.policy.minimum_candidate_confidence_level,
            "evidence_references": references,
            "qualification_timestamp": pattern.discovery_timestamp,
            "replay_identity": pattern.replay_identity,
            "contract_version": KNOWLEDGE_VERSION,
            "passive_evidence_only": True,
        }
        identity_body = {**values, "qualification_rationale": list(values["qualification_rationale"]),
                         "evidence_references": references.to_dict()}
        identifier = str(uuid5(NAMESPACE_URL, "pr207-candidate-knowledge:" + sha256(
            _canonical(identity_body)).hexdigest()))
        body = {"knowledge_uuid": identifier, **identity_body}
        return CandidateKnowledge(knowledge_uuid=identifier,
                                  sha256_digest=sha256(_canonical(body)).hexdigest(), **values)

    def _qualify(self, pattern: Pattern) -> tuple[str, tuple[str, ...]]:
        if pattern.pattern_type not in _KNOWN_PATTERN_TYPES:
            return "REJECTED", ("UNSUPPORTED_PATTERN_TYPE",)
        if pattern.configured_confidence_level < self.policy.minimum_candidate_confidence_level:
            return "REJECTED", ("CONFIGURED_CONFIDENCE_BELOW_CANDIDATE_THRESHOLD",)
        reasons = []
        if pattern.sample_count < self.policy.minimum_qualified_sample_count:
            reasons.append("SAMPLE_COUNT_BELOW_THRESHOLD_ELIGIBILITY")
        if pattern.configured_confidence_level < self.policy.minimum_configured_confidence_level:
            reasons.append("CONFIGURED_CONFIDENCE_BELOW_THRESHOLD_ELIGIBILITY")
        if reasons:
            return "CANDIDATE", tuple(reasons)
        return "THRESHOLD_ELIGIBLE", (
            "DECLARED_POLICY_THRESHOLDS_SATISFIED",
            "CONFIGURED_CONFIDENCE_IS_METADATA_NOT_STATISTICAL_CONFIDENCE",
        )


class KnowledgeRepository:
    """Atomic, fsync-protected, append-only candidate knowledge storage."""

    def __init__(self, root: str | Path = "operational_evidence") -> None:
        self.root = Path(root)

    def append(self, knowledge: CandidateKnowledge) -> Path:
        if type(knowledge) is not CandidateKnowledge:
            raise TypeError("CANDIDATE_KNOWLEDGE_REQUIRED")
        knowledge.__post_init__()
        directory = self.root / "candidate_knowledge"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"candidate_knowledge_{knowledge.knowledge_uuid}.json"
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(knowledge.canonical_bytes() + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise KnowledgeFormationError("DUPLICATE_KNOWLEDGE_IDENTITY") from exc
            if os.name != "nt":
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return path


__all__ = ["KNOWLEDGE_VERSION", "QUALIFICATION_POLICY_VERSION",
           "QUALIFICATION_STATUSES", "CandidateKnowledge",
           "EvidenceReferences", "KnowledgeFormationEngine", "KnowledgeFormationError",
           "KnowledgeQualificationPolicy", "KnowledgeRepository"]
