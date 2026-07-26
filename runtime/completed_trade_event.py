"""PR203 canonical event emitted after broker-confirmed trade completion.

Broker adapter objects terminate at :class:`CompletedTradeEventPublisher`.  The
published value is immutable, deterministic, and is the sole public input to
post-completion operational evidence consumers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from threading import Lock
from typing import Callable
from uuid import NAMESPACE_URL, UUID, uuid5


COMPLETED_TRADE_EVENT_VERSION = "PR203-COMPLETED-TRADE-EVENT.1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9._-]+$")


class CompletedTradeEventError(ValueError):
    """A fail-closed event construction, validation, or publication failure."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise CompletedTradeEventError("EVENT_SERIALIZATION_FAILURE") from exc


def _uuid(value: object, code: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (TypeError, ValueError, AttributeError) as exc:
        raise CompletedTradeEventError(code) from exc
    return value


def _time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # type: ignore[union-attr]
    except (TypeError, ValueError, AttributeError) as exc:
        raise CompletedTradeEventError("INVALID_EVENT_TIMESTAMP") from exc
    canonical = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed) or value != canonical:
        raise CompletedTradeEventError("INVALID_EVENT_TIMESTAMP")
    return parsed


@dataclass(frozen=True, slots=True)
class CompletedTradeEvent:
    """Canonical, broker-neutral fact describing one completed trade."""

    decision_uuid: str
    execution_context_uuid: str
    order_ticket: int
    deal_ticket: int
    position_ticket: int
    publication_uuid: str | None
    open_time: str
    close_time: str
    capture_time: str
    publication_timestamp: str | None
    consumer_acceptance_timestamp: str
    activation_timestamp: str
    order_send_timestamp: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    exit_reason: str
    stop_loss: float
    take_profit: float
    broker_response_code: str
    account_number: int
    server_name: str
    gross_profit: float
    net_profit: float
    commission: float
    swap: float
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    event_uuid: str
    sha256_digest: str
    replay_identity: str
    contract_version: str = COMPLETED_TRADE_EVENT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != COMPLETED_TRADE_EVENT_VERSION:
            raise CompletedTradeEventError("EVENT_VERSION_MISMATCH")
        for value in (self.decision_uuid, self.execution_context_uuid,
                      self.event_uuid, self.replay_identity):
            _uuid(value, "INVALID_EVENT_UUID")
        if self.publication_uuid is not None:
            _uuid(self.publication_uuid, "INVALID_EVENT_UUID")
        if (self.publication_uuid is None) != (self.publication_timestamp is None):
            raise CompletedTradeEventError("BROKEN_EVENT_PUBLICATION_IDENTITY")
        for ticket in (self.order_ticket, self.deal_ticket, self.position_ticket):
            if isinstance(ticket, bool) or not isinstance(ticket, int) or ticket <= 0:
                raise CompletedTradeEventError("INVALID_EVENT_TICKET")
        runtime_sequence = [
            _time(value) for value in (
                self.consumer_acceptance_timestamp, self.activation_timestamp,
                self.order_send_timestamp, self.open_time, self.close_time, self.capture_time
            )
        ]
        publication = _time(self.publication_timestamp) if self.publication_timestamp is not None else None
        if publication is not None and publication > runtime_sequence[0]:
            raise CompletedTradeEventError("INVALID_EVENT_TIMESTAMP_SEQUENCE")
        if any(left > right for left, right in zip(runtime_sequence, runtime_sequence[1:])):
            raise CompletedTradeEventError("INVALID_EVENT_TIMESTAMP_SEQUENCE")
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise CompletedTradeEventError("INVALID_EVENT_SYMBOL")
        if self.direction not in {"BUY", "SELL"}:
            raise CompletedTradeEventError("INVALID_EVENT_DIRECTION")
        for name in ("volume", "entry_price", "exit_price", "stop_loss", "take_profit",
                     "gross_profit", "net_profit", "commission", "swap"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise CompletedTradeEventError("INVALID_EVENT_NUMBER")
            if name in {"volume", "entry_price", "exit_price"} and value <= 0:
                raise CompletedTradeEventError("INVALID_EVENT_NUMBER")
            if name in {"stop_loss", "take_profit"} and value < 0:
                raise CompletedTradeEventError("INVALID_EVENT_NUMBER")
            object.__setattr__(self, name, float(value))
        for name in ("exit_reason", "broker_response_code", "server_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value.strip() != value:
                raise CompletedTradeEventError("INVALID_EVENT_BROKER_FACT")
        if isinstance(self.account_number, bool) or not isinstance(self.account_number, int) or self.account_number <= 0:
            raise CompletedTradeEventError("INVALID_EVENT_BROKER_FACT")
        for name in ("maximum_favorable_excursion", "maximum_adverse_excursion"):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                    raise CompletedTradeEventError("INVALID_EVENT_NUMBER")
                object.__setattr__(self, name, float(value))
        if not isinstance(self.exit_reason, str) or not self.exit_reason or self.exit_reason.strip() != self.exit_reason:
            raise CompletedTradeEventError("INVALID_EVENT_EXIT_REASON")
        expected_uuid = self.identity_uuid(self.replay_identity, self.order_ticket,
                                           self.deal_ticket, self.position_ticket)
        if self.event_uuid != expected_uuid:
            raise CompletedTradeEventError("EVENT_UUID_MISMATCH")
        expected_digest = sha256(_canonical(self._body())).hexdigest()
        if not _HEX64.fullmatch(self.sha256_digest) or self.sha256_digest != expected_digest:
            raise CompletedTradeEventError("EVENT_DIGEST_MISMATCH")

    @staticmethod
    def identity_uuid(replay_identity: str, order_ticket: int, deal_ticket: int,
                      position_ticket: int) -> str:
        identity = [replay_identity, order_ticket, deal_ticket, position_ticket]
        return str(uuid5(NAMESPACE_URL, f"pr203-completed-trade:{_canonical(identity).decode()}"))

    def _body(self) -> dict[str, object]:
        body = asdict(self)
        body.pop("sha256_digest")
        return body

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "sha256_digest": self.sha256_digest}

    def to_canonical_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    @classmethod
    def create(cls, **values: object) -> "CompletedTradeEvent":
        values = dict(values)
        for name in ("volume", "entry_price", "exit_price", "stop_loss", "take_profit",
                     "gross_profit", "net_profit", "commission", "swap",
                     "maximum_favorable_excursion", "maximum_adverse_excursion"):
            value = values.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[name] = float(value)
        event_uuid = cls.identity_uuid(values["replay_identity"], values["order_ticket"],
                                       values["deal_ticket"], values["position_ticket"])  # type: ignore[arg-type]
        unsigned = {**values, "event_uuid": event_uuid,
                    "contract_version": COMPLETED_TRADE_EVENT_VERSION}
        digest = sha256(_canonical(unsigned)).hexdigest()
        return cls(**unsigned, sha256_digest=digest)  # type: ignore[arg-type]


class CompletedTradeEventPublisher:
    """Production-host publication boundary with process-local duplicate rejection."""

    def __init__(self) -> None:
        self._observers: list[Callable[[CompletedTradeEvent], None]] = []
        self._published: set[str] = set()
        self._lock = Lock()

    def subscribe_completed_trade(self, observer: Callable[[CompletedTradeEvent], None]) -> None:
        if not callable(observer):
            raise TypeError("COMPLETED_TRADE_EVENT_OBSERVER_REQUIRED")
        self._observers.append(observer)

    def publish(self, event: CompletedTradeEvent) -> None:
        if type(event) is not CompletedTradeEvent:
            raise TypeError("COMPLETED_TRADE_EVENT_REQUIRED")
        # Reconstructing validates immutability and integrity at the host edge.
        event = CompletedTradeEvent(**event.to_dict())  # type: ignore[arg-type]
        with self._lock:
            if event.event_uuid in self._published:
                raise CompletedTradeEventError("DUPLICATE_COMPLETED_TRADE_EVENT")
            self._published.add(event.event_uuid)
        for observer in tuple(self._observers):
            observer(event)


__all__ = ["COMPLETED_TRADE_EVENT_VERSION", "CompletedTradeEvent",
           "CompletedTradeEventError", "CompletedTradeEventPublisher"]
