"""Passive, deterministic outcome evidence for completed trading positions.

This module is deliberately outside all runtime decision, risk, and execution
paths.  It correlates a completed trade result with a PR161 immutable decision
knowledge observation and optionally writes one append-only outcome record.
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
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from runtime.decision_knowledge_observation import (
    DecisionKnowledgeObservationRecord,
    KnowledgeObservation,
)
from runtime.knowledge_applicability import semver_major

DECISION_OUTCOME_OBSERVATION_CONTRACT_VERSION = "1.0.0"
OUTCOME_OBSERVATION_MODE = "OBSERVE_ONLY"
EXIT_REASONS = frozenset({"MANUAL_CLOSE", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP", "PARTIAL_CLOSE"})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9._-]+$")


class DecisionOutcomeObservationError(ValueError):
    """Fail-closed error raised when completed-trade evidence is invalid."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _uuid(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise DecisionOutcomeObservationError(code)
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise DecisionOutcomeObservationError(code) from exc
    return value


def _digest_value(value: object, code: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise DecisionOutcomeObservationError(code)
    return value


def _number(value: object, code: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DecisionOutcomeObservationError(code)
    value = float(value)
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise DecisionOutcomeObservationError(code)
    return value


def _timestamp(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise DecisionOutcomeObservationError(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionOutcomeObservationError(code) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DecisionOutcomeObservationError(code)
    normalized = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if value != normalized:
        raise DecisionOutcomeObservationError(code)
    return parsed


@dataclass(frozen=True)
class CompletedTradeResult:
    """Validated, read-only broker completion data used solely for observation."""

    decision_uuid: str
    decision_observation_uuid: str
    position_ticket: int
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    exit_reason: str

    def __post_init__(self) -> None:
        _uuid(self.decision_uuid, "MISSING_DECISION_UUID")
        _uuid(self.decision_observation_uuid, "MISSING_DECISION_OBSERVATION_UUID")
        if not isinstance(self.position_ticket, int) or isinstance(self.position_ticket, bool) or self.position_ticket <= 0:
            raise DecisionOutcomeObservationError("INVALID_POSITION_TICKET")
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise DecisionOutcomeObservationError("INVALID_SYMBOL")
        if self.direction not in {"BUY", "SELL"}:
            raise DecisionOutcomeObservationError("INVALID_DIRECTION")
        for name, positive, nonnegative in (("entry_price", True, False), ("exit_price", True, False),
                                             ("gross_profit", False, False), ("net_profit", False, False),
                                             ("commission", False, False), ("swap", False, False),
                                             ("maximum_favorable_excursion", False, True),
                                             ("maximum_adverse_excursion", False, True)):
            object.__setattr__(self, name, _number(getattr(self, name), "INVALID_PROFIT" if "profit" in name else "INVALID_TRADE_RESULT", positive=positive, nonnegative=nonnegative))
        entry = _timestamp(self.entry_time, "INVALID_ENTRY_TIME")
        exit_ = _timestamp(self.exit_time, "INVALID_EXIT_TIME")
        if exit_ < entry:
            raise DecisionOutcomeObservationError("INVALID_TIME")
        if self.exit_reason not in EXIT_REASONS:
            raise DecisionOutcomeObservationError("INVALID_EXIT_REASON")

    @property
    def holding_time_seconds(self) -> int:
        return int((_timestamp(self.exit_time, "INVALID_EXIT_TIME") - _timestamp(self.entry_time, "INVALID_ENTRY_TIME")).total_seconds())


@dataclass(frozen=True)
class DecisionOutcomeObservation:
    """Immutable authoritative evidence relating one completion to one decision."""

    decision_uuid: str
    decision_observation_uuid: str
    position_ticket: int
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    holding_time_seconds: int
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    exit_reason: str
    observation_digest: str = ""
    observation_uuid: str = ""
    contract_version: str = DECISION_OUTCOME_OBSERVATION_CONTRACT_VERSION
    observation_mode: str = OUTCOME_OBSERVATION_MODE

    def __post_init__(self) -> None:
        if semver_major(self.contract_version) != semver_major(DECISION_OUTCOME_OBSERVATION_CONTRACT_VERSION):
            raise DecisionOutcomeObservationError("UNSUPPORTED_OUTCOME_CONTRACT_VERSION")
        if self.observation_mode != OUTCOME_OBSERVATION_MODE:
            raise DecisionOutcomeObservationError("INVALID_OBSERVATION_MODE")
        result = CompletedTradeResult(self.decision_uuid, self.decision_observation_uuid, self.position_ticket,
            self.symbol, self.direction, self.entry_price, self.exit_price, self.entry_time, self.exit_time,
            self.gross_profit, self.net_profit, self.commission, self.swap, self.maximum_favorable_excursion,
            self.maximum_adverse_excursion, self.exit_reason)
        if not isinstance(self.holding_time_seconds, int) or isinstance(self.holding_time_seconds, bool) or self.holding_time_seconds != result.holding_time_seconds:
            raise DecisionOutcomeObservationError("INVALID_HOLDING_TIME")
        body = self._body()
        digest = _digest(body)
        identifier = str(uuid5(NAMESPACE_URL, f"decision-outcome-observation:{digest}"))
        if self.observation_digest and self.observation_digest != digest:
            raise DecisionOutcomeObservationError("OBSERVATION_DIGEST_MISMATCH")
        if self.observation_uuid and self.observation_uuid != identifier:
            raise DecisionOutcomeObservationError("OUTCOME_UUID_MISMATCH")
        object.__setattr__(self, "observation_digest", digest)
        object.__setattr__(self, "observation_uuid", identifier)

    def _body(self) -> dict[str, Any]:
        return {"contract_version": self.contract_version, "observation_mode": self.observation_mode,
                "decision_uuid": self.decision_uuid, "decision_observation_uuid": self.decision_observation_uuid,
                "position_ticket": self.position_ticket, "symbol": self.symbol, "direction": self.direction,
                "entry_price": self.entry_price, "exit_price": self.exit_price, "entry_time": self.entry_time,
                "exit_time": self.exit_time, "holding_time_seconds": self.holding_time_seconds,
                "gross_profit": self.gross_profit, "net_profit": self.net_profit, "commission": self.commission,
                "swap": self.swap, "maximum_favorable_excursion": self.maximum_favorable_excursion,
                "maximum_adverse_excursion": self.maximum_adverse_excursion, "exit_reason": self.exit_reason}

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "observation_digest": self.observation_digest, "observation_uuid": self.observation_uuid}


class DecisionOutcomeObservationRepository:
    """Atomically publishes canonical outcome JSON without replacement."""

    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    def append(self, record: DecisionOutcomeObservation) -> Path:
        if not isinstance(record, DecisionOutcomeObservation):
            raise TypeError("DECISION_OUTCOME_OBSERVATION_REQUIRED")
        directory = self.root / "decision_outcomes"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"outcome_{record.observation_uuid}.json"
        data = (_canonical(record.to_dict()) + "\n").encode("utf-8")
        if path.exists():
            if path.read_bytes() != data:
                raise FileExistsError("DECISION_OUTCOME_APPEND_ONLY")
            return path
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise FileExistsError("DECISION_OUTCOME_APPEND_ONLY")
            self._fsync_directory(directory)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class DecisionOutcomeObserver:
    """Passively correlates completed trade results and PR161 observations."""

    def __init__(self, repository: DecisionOutcomeObservationRepository | None = None) -> None:
        if repository is not None and not isinstance(repository, DecisionOutcomeObservationRepository):
            raise TypeError("DECISION_OUTCOME_REPOSITORY_REQUIRED")
        self._repository = repository

    def observe(self, trade_result: CompletedTradeResult,
                decision_observation: DecisionKnowledgeObservationRecord) -> DecisionOutcomeObservation:
        if not isinstance(trade_result, CompletedTradeResult):
            raise DecisionOutcomeObservationError("CORRUPTED_TRADE_RESULT")
        if not isinstance(decision_observation, DecisionKnowledgeObservationRecord):
            raise DecisionOutcomeObservationError("MISSING_DECISION_OBSERVATION")
        self._verify_decision_observation(decision_observation)
        if trade_result.decision_uuid != decision_observation.decision_uuid:
            raise DecisionOutcomeObservationError("DECISION_CORRELATION_MISMATCH")
        if trade_result.decision_observation_uuid != decision_observation.observation_uuid:
            raise DecisionOutcomeObservationError("OBSERVATION_CORRELATION_MISMATCH")
        record = DecisionOutcomeObservation(**asdict(trade_result), holding_time_seconds=trade_result.holding_time_seconds)
        if self._repository is not None:
            self._repository.append(record)
        return record

    @staticmethod
    def _verify_decision_observation(record: DecisionKnowledgeObservationRecord) -> None:
        try:
            verified = DecisionKnowledgeObservationRecord(record.decision_uuid, record.decision_cycle_uuid,
                record.decision_digest, record.report_uuid, record.report_digest, record.snapshot_digest,
                record.knowledge_observation, record.observation_timestamp, record.observation_digest,
                record.observation_uuid, record.contract_version, record.observation_mode)
        except (TypeError, ValueError, AttributeError) as exc:
            raise DecisionOutcomeObservationError("CORRUPTED_DECISION_OBSERVATION") from exc
        if verified != record or not isinstance(record.knowledge_observation, KnowledgeObservation):
            raise DecisionOutcomeObservationError("CORRUPTED_DECISION_OBSERVATION")


# Explicit aliases keep the public noun used by the architecture specification.
DecisionOutcomeObservationRecord = DecisionOutcomeObservation
TradeResult = CompletedTradeResult

__all__ = ["DECISION_OUTCOME_OBSERVATION_CONTRACT_VERSION", "OUTCOME_OBSERVATION_MODE", "EXIT_REASONS",
           "DecisionOutcomeObservationError", "CompletedTradeResult", "TradeResult", "DecisionOutcomeObservation",
           "DecisionOutcomeObservationRecord", "DecisionOutcomeObservationRepository", "DecisionOutcomeObserver"]
