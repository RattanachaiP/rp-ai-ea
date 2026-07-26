"""PR201 immutable capture of broker-confirmed completed-trade evidence.

This passive boundary is invoked after a broker has completed a position.  It
does not communicate with the broker and has no execution or decision authority.
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

from runtime.execution_contract import ExecutionContext


LIVE_OUTCOME_CONTRACT_VERSION = "PR201-LIVE-OUTCOME.1"
BROKER_EXECUTION_STATUS = "COMPLETED"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9._-]+$")


class LiveOutcomeCaptureError(ValueError):
    """A fail-closed live-outcome validation or capture failure."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise LiveOutcomeCaptureError("SERIALIZATION_FAILURE") from exc


def _uuid(value: object, code: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (TypeError, ValueError, AttributeError) as exc:
        raise LiveOutcomeCaptureError(code) from exc
    return value


def _time(value: object, code: str, *, optional: bool = False) -> datetime | None:
    if optional and value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # type: ignore[union-attr]
    except (TypeError, ValueError, AttributeError) as exc:
        raise LiveOutcomeCaptureError(code) from exc
    normalized = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed) or value != normalized:
        raise LiveOutcomeCaptureError(code)
    return parsed


def _number(value: object, code: str, *, positive: bool = False,
            nonnegative: bool = False, optional: bool = False) -> float | None:
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise LiveOutcomeCaptureError(code)
    result = float(value)
    if (positive and result <= 0) or (nonnegative and result < 0):
        raise LiveOutcomeCaptureError(code)
    return result


@dataclass(frozen=True, slots=True)
class BrokerCompletedTrade:
    """Read-only evidence supplied by the broker adapter after final settlement."""

    decision_uuid: str
    execution_context_uuid: str
    publication_uuid: str | None
    order_ticket: int
    deal_ticket: int
    position_ticket: int
    publication_timestamp: str | None
    consumer_acceptance_timestamp: str
    activation_timestamp: str
    order_send_timestamp: str
    position_open_timestamp: str
    position_close_timestamp: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    exit_reason: str
    broker_response_code: str
    broker_execution_status: str
    account_number: int
    server_name: str
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    replay_uuid: str
    parent_decision_uuid: str
    parent_execution_context_uuid: str

    def __post_init__(self) -> None:
        for name in ("decision_uuid", "execution_context_uuid", "replay_uuid",
                     "parent_decision_uuid", "parent_execution_context_uuid"):
            _uuid(getattr(self, name), "MISSING_UUID")
        _uuid(self.publication_uuid, "INVALID_PUBLICATION_UUID", optional=True)
        if (self.publication_uuid is None) != (self.publication_timestamp is None):
            raise LiveOutcomeCaptureError("BROKEN_PUBLICATION_IDENTITY")
        for name in ("order_ticket", "deal_ticket", "position_ticket", "account_number"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise LiveOutcomeCaptureError("MISSING_TICKET" if name != "account_number" else "INVALID_ACCOUNT_NUMBER")
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise LiveOutcomeCaptureError("INVALID_SYMBOL")
        if self.direction not in {"BUY", "SELL"}:
            raise LiveOutcomeCaptureError("INVALID_DIRECTION")
        for name in ("volume", "entry_price", "exit_price"):
            object.__setattr__(self, name, _number(getattr(self, name), "INVALID_EXECUTION_VALUE", positive=True))
        for name in ("stop_loss", "take_profit"):
            object.__setattr__(self, name, _number(getattr(self, name), "INVALID_EXECUTION_VALUE", nonnegative=True))
        for name in ("gross_profit", "net_profit", "commission", "swap"):
            object.__setattr__(self, name, _number(getattr(self, name), "INVALID_RESULT"))
        for name in ("maximum_favorable_excursion", "maximum_adverse_excursion"):
            object.__setattr__(self, name, _number(getattr(self, name), "INVALID_EXCURSION",
                                                   nonnegative=True, optional=True))
        for name in ("exit_reason", "broker_response_code", "server_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value.strip() != value:
                raise LiveOutcomeCaptureError("BROKER_CONFIRMATION_UNAVAILABLE")
        if self.broker_execution_status != BROKER_EXECUTION_STATUS:
            raise LiveOutcomeCaptureError("BROKER_CONFIRMATION_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class LiveOutcomeRecord:
    """Canonical authoritative operational evidence for one completed trade."""

    decision_uuid: str
    execution_context_uuid: str
    publication_uuid: str | None
    order_ticket: int
    deal_ticket: int
    position_ticket: int
    runtime_timestamp: str
    publication_timestamp: str | None
    consumer_acceptance_timestamp: str
    activation_timestamp: str
    order_send_timestamp: str
    position_open_timestamp: str
    position_close_timestamp: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    exit_reason: str
    execution_latency_seconds: float
    broker_response_code: str
    broker_execution_status: str
    account_number: int
    server_name: str
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    trade_duration_seconds: float
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    replay_identity_chain: tuple[str, str, str]
    parent_decision_uuid: str
    parent_execution_context_uuid: str
    captured_at: str
    record_digest: str = ""
    record_uuid: str = ""
    contract_version: str = LIVE_OUTCOME_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != LIVE_OUTCOME_CONTRACT_VERSION:
            raise LiveOutcomeCaptureError("CONTRACT_VERSION_MISMATCH")
        if not isinstance(self.replay_identity_chain, tuple) or len(self.replay_identity_chain) != 3:
            raise LiveOutcomeCaptureError("BROKEN_IDENTITY_CHAIN")
        for value in self.replay_identity_chain:
            _uuid(value, "BROKEN_IDENTITY_CHAIN")
        times = [_time(self.runtime_timestamp, "INVALID_TIMESTAMP_SEQUENCE")]
        publication = _time(self.publication_timestamp, "INVALID_TIMESTAMP_SEQUENCE", optional=True)
        if publication is not None:
            times.append(publication)
        times.extend(_time(getattr(self, name), "INVALID_TIMESTAMP_SEQUENCE") for name in (
            "consumer_acceptance_timestamp", "activation_timestamp", "order_send_timestamp",
            "position_open_timestamp", "position_close_timestamp", "captured_at"))
        if any(left > right for left, right in zip(times, times[1:])):  # type: ignore[operator]
            raise LiveOutcomeCaptureError("INVALID_TIMESTAMP_SEQUENCE")
        body = self._body()
        digest = sha256(_canonical(body)).hexdigest()
        # Broker/account ticket identity is stable even if a caller attempts to
        # recapture the same completion with a different capture timestamp.
        identity = (self.server_name, self.account_number, self.order_ticket,
                    self.deal_ticket, self.position_ticket)
        identifier = str(uuid5(NAMESPACE_URL, f"pr201-live-outcome:{_canonical(identity).decode('utf-8')}"))
        if self.record_digest and (not _HEX64.fullmatch(self.record_digest) or self.record_digest != digest):
            raise LiveOutcomeCaptureError("RECORD_DIGEST_MISMATCH")
        if self.record_uuid and self.record_uuid != identifier:
            raise LiveOutcomeCaptureError("RECORD_UUID_MISMATCH")
        object.__setattr__(self, "record_digest", digest)
        object.__setattr__(self, "record_uuid", identifier)

    def _body(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("record_digest")
        value.pop("record_uuid")
        value["replay_identity_chain"] = list(self.replay_identity_chain)
        return value

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "record_digest": self.record_digest, "record_uuid": self.record_uuid}


class LiveOutcomeRepository:
    """Atomically appends each record once; duplicates and replacement fail."""

    def __init__(self, root: str | Path = "operational_evidence") -> None:
        self.root = Path(root)

    def append(self, record: LiveOutcomeRecord) -> Path:
        if type(record) is not LiveOutcomeRecord:
            raise TypeError("LIVE_OUTCOME_RECORD_REQUIRED")
        directory = self.root / "live_outcomes"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"live_outcome_{record.record_uuid}.json"
        data = _canonical(record.to_dict()) + b"\n"
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise LiveOutcomeCaptureError("DUPLICATE_RECORD") from exc
            if os.name != "nt":
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return path


class LiveOutcomeCapture:
    """Validate and persist evidence without touching production execution."""

    def __init__(self, repository: LiveOutcomeRepository) -> None:
        if type(repository) is not LiveOutcomeRepository:
            raise TypeError("LIVE_OUTCOME_REPOSITORY_REQUIRED")
        self._repository = repository

    def capture(self, completed: BrokerCompletedTrade, context: ExecutionContext,
                *, captured_at: str) -> LiveOutcomeRecord:
        if type(completed) is not BrokerCompletedTrade:
            raise LiveOutcomeCaptureError("BROKER_CONFIRMATION_UNAVAILABLE")
        if type(context) is not ExecutionContext:
            raise LiveOutcomeCaptureError("BROKEN_IDENTITY_CHAIN")
        try:
            context = ExecutionContext(**context.to_dict())
        except (TypeError, ValueError, AttributeError) as exc:
            raise LiveOutcomeCaptureError("BROKEN_IDENTITY_CHAIN") from exc
        expected = (context.replay_uuid, context.decision_uuid, context.execution_uuid)
        if (completed.decision_uuid != context.decision_uuid
                or completed.execution_context_uuid != context.execution_uuid
                or completed.parent_decision_uuid != context.decision_uuid
                or completed.parent_execution_context_uuid != context.execution_uuid
                or completed.replay_uuid != context.replay_uuid):
            raise LiveOutcomeCaptureError("BROKEN_IDENTITY_CHAIN")
        opened = _time(completed.position_open_timestamp, "INVALID_TIMESTAMP_SEQUENCE")
        closed = _time(completed.position_close_timestamp, "INVALID_TIMESTAMP_SEQUENCE")
        sent = _time(completed.order_send_timestamp, "INVALID_TIMESTAMP_SEQUENCE")
        assert opened is not None and closed is not None and sent is not None
        values = asdict(completed)
        values.pop("replay_uuid")
        record = LiveOutcomeRecord(**values, runtime_timestamp=context.timestamp,
            execution_latency_seconds=(opened - sent).total_seconds(),
            trade_duration_seconds=(closed - opened).total_seconds(),
            replay_identity_chain=expected, captured_at=captured_at)
        self._repository.append(record)
        return record


__all__ = ["LIVE_OUTCOME_CONTRACT_VERSION", "BROKER_EXECUTION_STATUS", "LiveOutcomeCaptureError",
           "BrokerCompletedTrade", "LiveOutcomeRecord", "LiveOutcomeRepository", "LiveOutcomeCapture"]
