"""Broker-only validation for executor-owned order submission safety."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isclose, isfinite
from typing import Protocol


@dataclass(frozen=True)
class ExecutionInstruction:
    symbol: str
    direction: str
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class BrokerSymbol:
    trading_enabled: bool
    market_open: bool
    volume_min: float
    volume_max: float
    volume_step: float


@dataclass(frozen=True)
class OrderRequest:
    instruction: ExecutionInstruction
    execution_id: str
    comment: str


class BrokerOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    CONFIRMED_REJECTED_RETRYABLE = "CONFIRMED_REJECTED_RETRYABLE"
    CONFIRMED_REJECTED_FINAL = "CONFIRMED_REJECTED_FINAL"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class BrokerOrderResult:
    outcome: BrokerOutcome
    code: str
    ticket: str | None = None


class MT5ExecutionInterface(Protocol):
    def symbol_info(self, symbol: str) -> BrokerSymbol | None: ...
    def free_margin(self) -> float: ...
    def required_margin(self, instruction: ExecutionInstruction) -> float: ...
    def send_order(self, request: OrderRequest) -> BrokerOrderResult: ...


class BrokerSafety:
    """Validate broker facts only; analytical fields are intentionally absent."""

    def validate(self, instruction: ExecutionInstruction, broker: MT5ExecutionInterface) -> str | None:
        info = broker.symbol_info(instruction.symbol)
        if info is None:
            return "INVALID_SYMBOL"
        if not info.trading_enabled:
            return "TRADING_DISABLED"
        if not info.market_open:
            return "MARKET_CLOSED"
        if not self._valid_volume(instruction.volume, info):
            return "INVALID_LOT"
        if not self._valid_stops(instruction):
            return "INVALID_SL_TP"
        try:
            free_margin = broker.free_margin()
            required_margin = broker.required_margin(instruction)
        except Exception:
            return "BROKER_MARGIN_UNAVAILABLE"
        if not self._finite_non_negative(free_margin) or not self._finite_non_negative(required_margin):
            return "BROKER_MARGIN_UNAVAILABLE"
        if free_margin < required_margin:
            return "INSUFFICIENT_MARGIN"
        return None

    @staticmethod
    def _valid_volume(volume: float, info: BrokerSymbol) -> bool:
        if not all(BrokerSafety._finite_non_negative(value) for value in (volume, info.volume_min, info.volume_max, info.volume_step)):
            return False
        if info.volume_step <= 0 or volume < info.volume_min or volume > info.volume_max:
            return False
        steps = (volume - info.volume_min) / info.volume_step
        return isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-8)

    @staticmethod
    def _valid_stops(instruction: ExecutionInstruction) -> bool:
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
                   for value in (instruction.entry_price, instruction.stop_loss, instruction.take_profit)):
            return False
        if instruction.direction == "BUY":
            return instruction.stop_loss < instruction.entry_price < instruction.take_profit
        if instruction.direction == "SELL":
            return instruction.take_profit < instruction.entry_price < instruction.stop_loss
        return False

    @staticmethod
    def _finite_non_negative(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0
