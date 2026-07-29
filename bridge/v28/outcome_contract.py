"""Immutable, replay-safe contracts for completed-trade outcome evidence.

This module only describes observations.  It has no runtime, broker, strategy,
decision, risk, promotion, or learning authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from .execution_plan import parse_utc
from .pipeline_validator import certification_identity

OUTCOME_SCHEMA_VERSION = "V28.OUTCOME_RECORD.1.0"
OUTCOME_POLICY_REFERENCE = "V28_OUTCOME_INTELLIGENCE_POLICY@1.0.0"
EXIT_REASONS = frozenset({"STOP_LOSS", "TAKE_PROFIT", "MANUAL", "STRATEGY_EXIT", "BROKER_CLOSE", "MARKET_CLOSE", "OTHER"})


def _finite(value: Any, *, positive: bool = False, nonnegative: bool = False) -> None:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("OUTCOME_NUMERIC_INVALID")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError("OUTCOME_NUMERIC_INVALID")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in sorted(value.items())})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Opaque snapshot preserves upstream evidence without re-owning its semantics."""
    source_identity: str
    captured_payload: Mapping[str, Any]
    snapshot_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {"source_identity": self.source_identity, "captured_payload": self.captured_payload}

    def __post_init__(self) -> None:
        if not self.source_identity or not isinstance(self.captured_payload, Mapping):
            raise ValueError("OUTCOME_SNAPSHOT_INVALID")
        object.__setattr__(self, "captured_payload", _freeze(self.captured_payload))
        if self.snapshot_identity != certification_identity("V28_OUTCOME_EVIDENCE_SNAPSHOT", self.canonical_payload()):
            raise ValueError("OUTCOME_SNAPSHOT_IDENTITY_INVALID")


def create_evidence_snapshot(*, source_identity: str, captured_payload: Mapping[str, Any]) -> EvidenceSnapshot:
    values = {"source_identity": source_identity, "captured_payload": _freeze(captured_payload)}
    return EvidenceSnapshot(**values, snapshot_identity=certification_identity("V28_OUTCOME_EVIDENCE_SNAPSHOT", values))


@dataclass(frozen=True)
class EntryEvidence:
    order_identity: str
    observed_at: str
    requested_price: float
    filled_price: float
    spread: float
    slippage: float
    evidence_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "evidence_identity"}

    def __post_init__(self) -> None:
        parse_utc(self.observed_at)
        if not self.order_identity:
            raise ValueError("ENTRY_EVIDENCE_INVALID")
        for value in (self.requested_price, self.filled_price): _finite(value, positive=True)
        for value in (self.spread, self.slippage): _finite(value, nonnegative=True)
        if self.evidence_identity != certification_identity("V28_OUTCOME_ENTRY_EVIDENCE", self.canonical_payload()):
            raise ValueError("ENTRY_EVIDENCE_IDENTITY_INVALID")


@dataclass(frozen=True)
class ExitEvidence:
    deal_identity: str
    observed_at: str
    requested_price: float
    filled_price: float
    exit_reason: str
    slippage: float
    evidence_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "evidence_identity"}

    def __post_init__(self) -> None:
        parse_utc(self.observed_at)
        if not self.deal_identity or self.exit_reason not in EXIT_REASONS:
            raise ValueError("EXIT_EVIDENCE_INVALID")
        for value in (self.requested_price, self.filled_price): _finite(value, positive=True)
        _finite(self.slippage, nonnegative=True)
        if self.evidence_identity != certification_identity("V28_OUTCOME_EXIT_EVIDENCE", self.canonical_payload()):
            raise ValueError("EXIT_EVIDENCE_IDENTITY_INVALID")


def create_entry_evidence(**values: Any) -> EntryEvidence:
    return EntryEvidence(**values, evidence_identity=certification_identity("V28_OUTCOME_ENTRY_EVIDENCE", values))


def create_exit_evidence(**values: Any) -> ExitEvidence:
    return ExitEvidence(**values, evidence_identity=certification_identity("V28_OUTCOME_EXIT_EVIDENCE", values))


@dataclass(frozen=True)
class TradeLifecycleRecord:
    trade_identity: str
    entry: EntryEvidence
    exit: ExitEvidence
    lifecycle_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "lifecycle_identity"}

    def __post_init__(self) -> None:
        EntryEvidence(**self.entry.__dict__); ExitEvidence(**self.exit.__dict__)
        if not self.trade_identity or parse_utc(self.exit.observed_at) < parse_utc(self.entry.observed_at):
            raise ValueError("TRADE_LIFECYCLE_INVALID")
        if self.lifecycle_identity != certification_identity("V28_TRADE_LIFECYCLE", self.canonical_payload()):
            raise ValueError("TRADE_LIFECYCLE_IDENTITY_INVALID")


def create_trade_lifecycle(*, trade_identity: str, entry: EntryEvidence, exit: ExitEvidence) -> TradeLifecycleRecord:
    values = {"trade_identity": trade_identity, "entry": entry, "exit": exit}
    return TradeLifecycleRecord(**values, lifecycle_identity=certification_identity("V28_TRADE_LIFECYCLE", values))


@dataclass(frozen=True)
class TradeResult:
    gross_profit: float
    commission: float
    swap: float
    net_profit: float
    initial_risk: float
    r_multiple: float
    holding_time_seconds: float
    result_identity: str

    def canonical_payload(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "result_identity"}

    def __post_init__(self) -> None:
        for value in (self.gross_profit, self.commission, self.swap, self.net_profit, self.r_multiple): _finite(value)
        _finite(self.initial_risk, positive=True); _finite(self.holding_time_seconds, nonnegative=True)
        if abs(self.net_profit - (self.gross_profit + self.commission + self.swap)) > 1e-9:
            raise ValueError("TRADE_RESULT_NET_INVALID")
        if abs(self.r_multiple - self.net_profit / self.initial_risk) > 1e-9:
            raise ValueError("TRADE_RESULT_R_MULTIPLE_INVALID")
        if self.result_identity != certification_identity("V28_TRADE_RESULT", self.canonical_payload()):
            raise ValueError("TRADE_RESULT_IDENTITY_INVALID")


def create_trade_result(*, gross_profit: float, commission: float, swap: float,
                        initial_risk: float, entry_time: str, exit_time: str) -> TradeResult:
    _finite(initial_risk, positive=True)
    holding = (parse_utc(exit_time) - parse_utc(entry_time)).total_seconds()
    net = gross_profit + commission + swap
    values = dict(gross_profit=gross_profit, commission=commission, swap=swap, net_profit=net,
                  initial_risk=initial_risk, r_multiple=net / initial_risk, holding_time_seconds=holding)
    return TradeResult(**values, result_identity=certification_identity("V28_TRADE_RESULT", values))


@dataclass(frozen=True)
class OutcomeRecord:
    trade_identity: str; symbol: str; direction: str
    entry_time: str; exit_time: str; entry_price: float; exit_price: float
    stop_loss: float; take_profit: float; position_size: float
    spread: float; slippage: float; lifecycle: TradeLifecycleRecord; result: TradeResult
    runtime_snapshot: EvidenceSnapshot; market_regime_snapshot: EvidenceSnapshot
    opportunity_snapshot: EvidenceSnapshot; decision_snapshot: EvidenceSnapshot
    risk_snapshot: EvidenceSnapshot; execution_snapshot: EvidenceSnapshot
    confidence: float; execution_plan_identity: str; qualification_identity: str; readiness_identity: str
    outcome_identity: str; policy_reference: str = OUTCOME_POLICY_REFERENCE
    schema_version: str = OUTCOME_SCHEMA_VERSION

    def canonical_payload(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "outcome_identity"}

    def __post_init__(self) -> None:
        TradeLifecycleRecord(**self.lifecycle.__dict__); TradeResult(**self.result.__dict__)
        snapshots = (self.runtime_snapshot, self.market_regime_snapshot, self.opportunity_snapshot,
                     self.decision_snapshot, self.risk_snapshot, self.execution_snapshot)
        for snapshot in snapshots: EvidenceSnapshot(**snapshot.__dict__)
        if self.schema_version != OUTCOME_SCHEMA_VERSION or self.policy_reference != OUTCOME_POLICY_REFERENCE:
            raise ValueError("OUTCOME_VERSION_INVALID")
        if (not self.trade_identity or not self.symbol or self.direction not in {"BUY", "SELL"} or
                not all((self.execution_plan_identity, self.qualification_identity, self.readiness_identity))):
            raise ValueError("OUTCOME_IDENTITY_FIELDS_INVALID")
        if self.lifecycle.trade_identity != self.trade_identity:
            raise ValueError("OUTCOME_LIFECYCLE_MISMATCH")
        if (self.entry_time, self.exit_time, self.entry_price, self.exit_price) != (
                self.lifecycle.entry.observed_at, self.lifecycle.exit.observed_at,
                self.lifecycle.entry.filled_price, self.lifecycle.exit.filled_price):
            raise ValueError("OUTCOME_LIFECYCLE_FIELDS_MISMATCH")
        expected_holding = (parse_utc(self.exit_time) - parse_utc(self.entry_time)).total_seconds()
        if self.result.holding_time_seconds != expected_holding:
            raise ValueError("OUTCOME_HOLDING_TIME_MISMATCH")
        for value in (self.entry_price, self.exit_price, self.stop_loss, self.take_profit, self.position_size): _finite(value, positive=True)
        for value in (self.spread, self.slippage): _finite(value, nonnegative=True)
        _finite(self.confidence, nonnegative=True)
        if self.confidence > 1 or self.spread != self.lifecycle.entry.spread or self.slippage != self.lifecycle.entry.slippage + self.lifecycle.exit.slippage:
            raise ValueError("OUTCOME_EXECUTION_FIELDS_INVALID")
        if self.execution_snapshot.source_identity != self.execution_plan_identity:
            raise ValueError("OUTCOME_EXECUTION_LINEAGE_INVALID")
        if self.outcome_identity != certification_identity("V28_OUTCOME_RECORD", self.canonical_payload()):
            raise ValueError("OUTCOME_RECORD_IDENTITY_INVALID")


def create_outcome_record(**values: Any) -> OutcomeRecord:
    values.setdefault("policy_reference", OUTCOME_POLICY_REFERENCE)
    values.setdefault("schema_version", OUTCOME_SCHEMA_VERSION)
    return OutcomeRecord(**values, outcome_identity=certification_identity("V28_OUTCOME_RECORD", values))
