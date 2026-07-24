"""Passive, deterministic audit records for Decision Knowledge Interface reads.

This module is deliberately outside the decision construction path.  It reads
only the public DKI contract and returns/persists an immutable audit record;
it never returns data that can alter a trading decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from runtime.decision_knowledge_interface import (
    DECISION_KNOWLEDGE_CONTRACT_VERSION,
    DecisionKnowledgeAccessError,
    DecisionKnowledgeInterface,
    DecisionKnowledgeRecord,
)
from runtime.knowledge_applicability import semver_major


DECISION_KNOWLEDGE_OBSERVATION_CONTRACT_VERSION = "1.0.0"
OBSERVATION_MODE = "OBSERVE_ONLY"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DecisionKnowledgeObservationError(ValueError):
    """Fail-closed error raised when an observation cannot be trusted."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionKnowledgeObservationError(code)
    return value.strip()


def _uuid(value: object, code: str) -> str:
    result = _identifier(value, code)
    try:
        if str(UUID(result)) != result:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise DecisionKnowledgeObservationError(code) from exc
    return result


def _digest_value(value: object, code: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise DecisionKnowledgeObservationError(code)
    return value


def _timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_TIMESTAMP")
    normalized = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if value != normalized:
        raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_TIMESTAMP")
    return value


@dataclass(frozen=True)
class ObservedKnowledgeReference:
    """The immutable, metadata-free DKI record retained by an observation."""

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
        object.__setattr__(self, "knowledge_uuid", _identifier(self.knowledge_uuid, "INVALID_KNOWLEDGE_IDENTITY"))
        object.__setattr__(self, "semantic_identity", _identifier(self.semantic_identity, "INVALID_SEMANTIC_IDENTITY"))
        if (isinstance(self.applicability_score, bool) or not isinstance(self.applicability_score, (int, float))
                or not isfinite(self.applicability_score) or not 0 <= self.applicability_score <= 1):
            raise DecisionKnowledgeObservationError("INVALID_APPLICABILITY_SCORE")
        if (isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float))
                or not isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise DecisionKnowledgeObservationError("INVALID_CONFIDENCE")
        if (not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority < 0
                or not isinstance(self.registry_sequence, int) or isinstance(self.registry_sequence, bool)
                or self.registry_sequence < 1):
            raise DecisionKnowledgeObservationError("INVALID_KNOWLEDGE_REFERENCE")
        for value, code in ((self.matching_factors, "INVALID_MATCHING_FACTORS"), (self.reason_codes, "INVALID_REASON_CODES")):
            if not isinstance(value, tuple) or any(not isinstance(item, str) or not item for item in value):
                raise DecisionKnowledgeObservationError(code)
        _digest_value(self.snapshot_digest, "INVALID_SNAPSHOT_DIGEST")
        object.__setattr__(self, "applicability_score", float(self.applicability_score))
        object.__setattr__(self, "confidence", float(self.confidence))

    @classmethod
    def from_dki(cls, item: DecisionKnowledgeRecord) -> "ObservedKnowledgeReference":
        if not isinstance(item, DecisionKnowledgeRecord):
            raise DecisionKnowledgeObservationError("CORRUPTED_DKI")
        return cls(**asdict(item))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["matching_factors"] = list(self.matching_factors)
        result["reason_codes"] = list(self.reason_codes)
        return result


@dataclass(frozen=True)
class KnowledgeObservation:
    """Immutable knowledge-only section of an observation record."""

    applicable_knowledge: tuple[ObservedKnowledgeReference, ...]
    resolved_knowledge: tuple[ObservedKnowledgeReference, ...]
    observation_status: str

    def __post_init__(self) -> None:
        for value in (self.applicable_knowledge, self.resolved_knowledge):
            if not isinstance(value, tuple) or any(not isinstance(item, ObservedKnowledgeReference) for item in value):
                raise DecisionKnowledgeObservationError("INVALID_KNOWLEDGE_OBSERVATION")
        expected = tuple(sorted(self.applicable_knowledge, key=lambda item: (
            -item.priority, -item.applicability_score, -item.confidence, item.semantic_identity, item.knowledge_uuid,
        )))
        if self.applicable_knowledge != expected or self.resolved_knowledge != expected:
            raise DecisionKnowledgeObservationError("NON_CANONICAL_OBSERVED_KNOWLEDGE_ORDER")
        identities = [(item.knowledge_uuid, item.semantic_identity) for item in self.applicable_knowledge]
        if len({item[0] for item in identities}) != len(identities):
            raise DecisionKnowledgeObservationError("DUPLICATE_KNOWLEDGE_IDENTITY")
        if len({item[1] for item in identities}) != len(identities):
            raise DecisionKnowledgeObservationError("DUPLICATE_SEMANTIC_IDENTITY")
        if self.observation_status not in {"OBSERVED", "EMPTY"} or (self.observation_status == "EMPTY") != (not identities):
            raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_STATUS")

    def to_dict(self) -> dict[str, Any]:
        return {"applicable_knowledge": [item.to_dict() for item in self.applicable_knowledge],
                "resolved_knowledge": [item.to_dict() for item in self.resolved_knowledge],
                "observation_status": self.observation_status}


@dataclass(frozen=True)
class DecisionKnowledgeObservationRecord:
    """Complete append-only audit record for one decision/DKI observation."""

    decision_uuid: str
    decision_cycle_uuid: str
    decision_digest: str
    report_uuid: str
    report_digest: str
    snapshot_digest: str
    knowledge_observation: KnowledgeObservation
    observation_timestamp: str
    observation_digest: str = ""
    observation_uuid: str = ""
    contract_version: str = DECISION_KNOWLEDGE_OBSERVATION_CONTRACT_VERSION
    observation_mode: str = OBSERVATION_MODE

    def __post_init__(self) -> None:
        if semver_major(self.contract_version) != semver_major(DECISION_KNOWLEDGE_OBSERVATION_CONTRACT_VERSION):
            raise DecisionKnowledgeObservationError("UNSUPPORTED_OBSERVATION_CONTRACT_VERSION")
        if self.observation_mode != OBSERVATION_MODE:
            raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_MODE")
        _uuid(self.decision_uuid, "INVALID_DECISION_UUID")
        _uuid(self.decision_cycle_uuid, "INVALID_DECISION_CYCLE_UUID")
        _uuid(self.report_uuid, "INVALID_REPORT_UUID")
        for value, code in ((self.decision_digest, "INVALID_DECISION_DIGEST"), (self.report_digest, "INVALID_REPORT_DIGEST"),
                            (self.snapshot_digest, "INVALID_SNAPSHOT_DIGEST")):
            _digest_value(value, code)
        if not isinstance(self.knowledge_observation, KnowledgeObservation):
            raise DecisionKnowledgeObservationError("INVALID_KNOWLEDGE_OBSERVATION")
        if any(item.snapshot_digest != self.snapshot_digest for item in self.knowledge_observation.applicable_knowledge):
            raise DecisionKnowledgeObservationError("SNAPSHOT_PROVENANCE_MISMATCH")
        _timestamp(self.observation_timestamp)
        body = self._body()
        digest = _digest(body)
        identifier = str(uuid5(NAMESPACE_URL, f"decision-knowledge-observation:{digest}"))
        if self.observation_digest and self.observation_digest != digest:
            raise DecisionKnowledgeObservationError("OBSERVATION_DIGEST_MISMATCH")
        if self.observation_uuid and self.observation_uuid != identifier:
            raise DecisionKnowledgeObservationError("OBSERVATION_UUID_MISMATCH")
        object.__setattr__(self, "observation_digest", digest)
        object.__setattr__(self, "observation_uuid", identifier)

    def _body(self) -> dict[str, Any]:
        return {"contract_version": self.contract_version, "observation_mode": self.observation_mode,
                "decision_uuid": self.decision_uuid, "decision_cycle_uuid": self.decision_cycle_uuid,
                "decision_digest": self.decision_digest, "report_uuid": self.report_uuid,
                "report_digest": self.report_digest, "snapshot_digest": self.snapshot_digest,
                "knowledge_observation": self.knowledge_observation.to_dict(),
                "observation_timestamp": self.observation_timestamp}

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "observation_digest": self.observation_digest, "observation_uuid": self.observation_uuid}


class DecisionKnowledgeObservationRepository:
    """Durably publishes immutable records without replacing an existing one."""
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    def append(self, record: DecisionKnowledgeObservationRecord) -> Path:
        if not isinstance(record, DecisionKnowledgeObservationRecord):
            raise TypeError("DECISION_KNOWLEDGE_OBSERVATION_RECORD_REQUIRED")
        directory = self.root / "decision_knowledge_observations"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"observation_{record.observation_uuid}.json"
        data = (_canonical(record.to_dict()) + "\n").encode("utf-8")
        if path.exists():
            if path.read_bytes() != data:
                raise FileExistsError("DECISION_KNOWLEDGE_OBSERVATION_APPEND_ONLY")
            return path
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise FileExistsError("DECISION_KNOWLEDGE_OBSERVATION_APPEND_ONLY")
            self._fsync_directory(directory)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)


class DecisionKnowledgeObserver:
    """Orchestrates DKI reads and optional append-only persistence, passively."""
    def __init__(self, repository: DecisionKnowledgeObservationRepository | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if repository is not None and not isinstance(repository, DecisionKnowledgeObservationRepository):
            raise TypeError("DECISION_KNOWLEDGE_OBSERVATION_REPOSITORY_REQUIRED")
        self._repository, self._clock = repository, clock or (lambda: datetime.now(timezone.utc))

    def observe(self, dki: DecisionKnowledgeInterface, *, decision_uuid: str, decision_cycle_uuid: str,
                decision_digest: str, observation_timestamp: str | None = None) -> DecisionKnowledgeObservationRecord:
        if not isinstance(dki, DecisionKnowledgeInterface):
            raise DecisionKnowledgeObservationError("MISSING_DKI")
        try:
            report_uuid, report_digest, snapshot_digest = dki.report_uuid(), dki.report_digest(), dki.snapshot_digest()
            _uuid(report_uuid, "INVALID_REPORT_UUID")
            _digest_value(report_digest, "INVALID_REPORT_DIGEST")
            _digest_value(snapshot_digest, "INVALID_SNAPSHOT_DIGEST")
            items = dki.list_applicable()
            observed = tuple(ObservedKnowledgeReference.from_dki(item) for item in items)
            resolved = tuple(ObservedKnowledgeReference.from_dki(dki.resolve(item.semantic_identity)) for item in observed)
            for item in observed:
                if dki.lookup(item.knowledge_uuid) != next(value for value in items if value.knowledge_uuid == item.knowledge_uuid):
                    raise DecisionKnowledgeObservationError("CORRUPTED_DKI")
        except (DecisionKnowledgeAccessError, DecisionKnowledgeObservationError, AttributeError, StopIteration, TypeError, ValueError) as exc:
            raise DecisionKnowledgeObservationError("CORRUPTED_DKI") from exc
        observation = KnowledgeObservation(observed, resolved, "OBSERVED" if observed else "EMPTY")
        timestamp = observation_timestamp if observation_timestamp is not None else self._now()
        record = DecisionKnowledgeObservationRecord(decision_uuid, decision_cycle_uuid, decision_digest,
            report_uuid, report_digest, snapshot_digest, observation, timestamp)
        if self._repository is not None:
            self._repository.append(record)
        return record

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise DecisionKnowledgeObservationError("INVALID_OBSERVATION_CLOCK")
        value = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = ["DECISION_KNOWLEDGE_OBSERVATION_CONTRACT_VERSION", "OBSERVATION_MODE",
           "DecisionKnowledgeObservationError", "ObservedKnowledgeReference", "KnowledgeObservation",
           "DecisionKnowledgeObservationRecord", "DecisionKnowledgeObservationRepository", "DecisionKnowledgeObserver"]
