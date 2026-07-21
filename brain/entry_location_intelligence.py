"""Entry Location Intelligence (ELI) Phase 1 pure domain model.

ELI assesses whether an already-selected direction has a safe location for an
entry.  It does not create signals, send orders, publish runtime payloads, or
change Adaptive Position Construction (APC).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class EntryState(str, Enum):
    ENTRY_ALLOWED = "ENTRY_ALLOWED"
    WAIT_PULLBACK = "WAIT_PULLBACK"
    WAIT_CONFIRMATION = "WAIT_CONFIRMATION"
    BLOCK_SWING_EXTREME = "BLOCK_SWING_EXTREME"
    BLOCK_ATR_EXTENSION = "BLOCK_ATR_EXTENSION"
    BLOCK_POOR_RR = "BLOCK_POOR_RR"
    BLOCK_INVALID_GEOMETRY = "BLOCK_INVALID_GEOMETRY"


@dataclass(frozen=True)
class EntryLocationConfig:
    """Named, conservative ELI safety thresholds."""

    buy_upper_swing_block: float = 0.90
    sell_lower_swing_block: float = 0.10
    severe_extension_atr: float = 2.0
    hard_extension_atr: float = 2.5
    minimum_rr: float = 1.20


@dataclass(frozen=True)
class EntryLocationInput:
    direction: str
    current_price: float
    swing_high: float
    swing_low: float
    atr: float
    recent_impulse_start: float
    recent_impulse_end: float
    pullback_detected: bool
    pullback_confirmed: bool
    structure_confirmed: bool
    liquidity_sweep_up: bool
    liquidity_sweep_down: bool
    nearest_support: float
    nearest_resistance: float
    expected_target: float
    invalidation_price: float
    execution_confidence: float


@dataclass(frozen=True)
class EntryLocationAssessment:
    location_score: float
    entry_permission: bool
    entry_state: EntryState
    reasons: tuple[str, ...]
    component_scores: dict[str, float]
    swing_position: float | None
    atr_extension: float | None
    risk_reward: float | None
    direction: str = ""


class SwingLocationEngine:
    def calculate(self, current_price: float, swing_low: float, swing_high: float) -> float:
        return (current_price - swing_low) / (swing_high - swing_low)


class AtrExtensionEngine:
    def calculate(self, direction: str, impulse_start: float, impulse_end: float, atr: float) -> float:
        movement = impulse_end - impulse_start
        directional_movement = movement if direction == "BUY" else -movement
        return max(0.0, directional_movement / atr)


class PullbackAssessmentEngine:
    def state(self, data: EntryLocationInput, extension: float, config: EntryLocationConfig) -> tuple[str, float]:
        if data.pullback_confirmed and data.structure_confirmed:
            return "CONTINUATION_CONFIRMED", 20.0
        if data.pullback_confirmed:
            return "PULLBACK_CONFIRMED", 14.0
        if data.pullback_detected:
            return "PULLBACK_UNCONFIRMED", 6.0
        # A fresh, structurally confirmed trend start is intentionally eligible;
        # the exception does not apply to an extended impulse.
        if data.structure_confirmed and extension < config.severe_extension_atr:
            return "TREND_START_CONFIRMED", 16.0
        return "NO_PULLBACK", 0.0


class LocationQualityEngine:
    """Combines named, bounded components rather than an opaque score."""

    def score(self, components: dict[str, float]) -> float:
        return round(max(0.0, min(100.0, sum(components.values()))), 2)


class EntryLocationIntelligence:
    """Deterministically evaluate directional entry location without side effects."""

    def __init__(self, config: EntryLocationConfig | None = None) -> None:
        self.config = config or EntryLocationConfig()
        self.swing = SwingLocationEngine()
        self.extension = AtrExtensionEngine()
        self.pullback = PullbackAssessmentEngine()
        self.quality = LocationQualityEngine()

    def assess(self, data: EntryLocationInput) -> EntryLocationAssessment:
        invalid = self._invalid_reason(data)
        if invalid:
            return self._blocked_invalid(invalid, direction=data.direction if isinstance(data, EntryLocationInput) else "")

        swing_position = self.swing.calculate(data.current_price, data.swing_low, data.swing_high)
        extension = self.extension.calculate(data.direction, data.recent_impulse_start, data.recent_impulse_end, data.atr)
        rr = self._risk_reward(data)
        if rr is None:
            return self._blocked_invalid("INVALID_TARGET_INVALIDATION_GEOMETRY", swing_position, extension, data.direction)

        components = self._components(data, swing_position, extension, rr)
        score = self.quality.score(components)
        reasons: list[str] = []

        if (data.direction == "BUY" and swing_position >= self.config.buy_upper_swing_block) or (
            data.direction == "SELL" and swing_position <= self.config.sell_lower_swing_block
        ):
            return self._assessment(score, False, EntryState.BLOCK_SWING_EXTREME, reasons + [
                "BUY_NEAR_SWING_HIGH" if data.direction == "BUY" else "SELL_NEAR_SWING_LOW"
            ], components, swing_position, extension, rr, data.direction)
        if rr < self.config.minimum_rr:
            return self._assessment(score, False, EntryState.BLOCK_POOR_RR, reasons + ["RISK_REWARD_BELOW_MINIMUM"], components, swing_position, extension, rr, data.direction)

        pullback_state, _ = self.pullback.state(data, extension, self.config)
        continuation = pullback_state == "CONTINUATION_CONFIRMED"
        if extension >= self.config.hard_extension_atr and not continuation:
            return self._assessment(score, False, EntryState.BLOCK_ATR_EXTENSION, reasons + ["EXCESSIVE_DIRECTIONAL_ATR_EXTENSION", "CONTINUATION_NOT_CONFIRMED"], components, swing_position, extension, rr, data.direction)
        if data.direction == "BUY" and data.liquidity_sweep_up and not continuation:
            return self._assessment(score, False, EntryState.WAIT_CONFIRMATION, reasons + ["UPPER_LIQUIDITY_SWEEP_REQUIRES_CONFIRMATION"], components, swing_position, extension, rr, data.direction)
        if data.direction == "SELL" and data.liquidity_sweep_down and not continuation:
            return self._assessment(score, False, EntryState.WAIT_CONFIRMATION, reasons + ["LOWER_LIQUIDITY_SWEEP_REQUIRES_CONFIRMATION"], components, swing_position, extension, rr, data.direction)
        if extension >= self.config.severe_extension_atr and not continuation:
            return self._assessment(score, False, EntryState.WAIT_PULLBACK, reasons + ["DIRECTIONAL_ATR_EXTENSION_REQUIRES_PULLBACK"], components, swing_position, extension, rr, data.direction)
        if pullback_state == "NO_PULLBACK":
            return self._assessment(score, False, EntryState.WAIT_PULLBACK, reasons + ["PULLBACK_NOT_DETECTED"], components, swing_position, extension, rr, data.direction)
        if pullback_state == "PULLBACK_UNCONFIRMED":
            return self._assessment(score, False, EntryState.WAIT_CONFIRMATION, reasons + ["PULLBACK_NOT_CONFIRMED"], components, swing_position, extension, rr, data.direction)
        if not data.structure_confirmed:
            return self._assessment(score, False, EntryState.WAIT_CONFIRMATION, reasons + ["STRUCTURE_NOT_CONFIRMED"], components, swing_position, extension, rr, data.direction)
        return self._assessment(score, True, EntryState.ENTRY_ALLOWED, reasons + [pullback_state], components, swing_position, extension, rr, data.direction)

    def _components(self, data: EntryLocationInput, swing_position: float, extension: float, rr: float) -> dict[str, float]:
        directional_swing = 1.0 - swing_position if data.direction == "BUY" else swing_position
        _, pullback_score = self.pullback.state(data, extension, self.config)
        nearest_favourable = data.nearest_support if data.direction == "BUY" else data.nearest_resistance
        nearest_opposing = data.nearest_resistance if data.direction == "BUY" else data.nearest_support
        support_resistance = 10.0 if abs(data.current_price - nearest_favourable) <= abs(nearest_opposing - data.current_price) else 3.0
        return {
            "swing_location": round(max(0.0, min(25.0, directional_swing * 25.0)), 2),
            "atr_extension": 20.0 if extension < self.config.severe_extension_atr else (8.0 if extension < self.config.hard_extension_atr else 0.0),
            "pullback": pullback_score,
            "structure_confirmation": 10.0 if data.structure_confirmed else 0.0,
            "liquidity_context": 0.0 if (data.direction == "BUY" and data.liquidity_sweep_up) or (data.direction == "SELL" and data.liquidity_sweep_down) else 5.0,
            "risk_reward": round(min(15.0, rr / self.config.minimum_rr * 15.0), 2),
            "support_resistance_distance": support_resistance,
            "execution_confidence": round(min(10.0, max(0.0, data.execution_confidence / 10.0)), 2),
        }

    @staticmethod
    def _risk_reward(data: EntryLocationInput) -> float | None:
        risk = data.current_price - data.invalidation_price if data.direction == "BUY" else data.invalidation_price - data.current_price
        reward = data.expected_target - data.current_price if data.direction == "BUY" else data.current_price - data.expected_target
        return reward / risk if risk > 0 and reward > 0 else None

    @staticmethod
    def _numbers(data: EntryLocationInput) -> tuple[float, ...]:
        return (data.current_price, data.swing_high, data.swing_low, data.atr, data.recent_impulse_start, data.recent_impulse_end, data.nearest_support, data.nearest_resistance, data.expected_target, data.invalidation_price, data.execution_confidence)

    def _invalid_reason(self, data: EntryLocationInput) -> str | None:
        if not isinstance(data, EntryLocationInput): return "INVALID_INPUT_TYPE"
        if data.direction not in {"BUY", "SELL"}: return "INVALID_DIRECTION"
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in self._numbers(data)): return "INVALID_NUMERIC_INPUT"
        if data.swing_high <= data.swing_low: return "INVALID_SWING_RANGE"
        if data.atr <= 0: return "INVALID_ATR"
        if not data.swing_low <= data.current_price <= data.swing_high: return "PRICE_OUTSIDE_SWING_RANGE"
        return None

    @staticmethod
    def _assessment(score: float, permission: bool, state: EntryState, reasons: list[str], components: dict[str, float], swing: float | None, extension: float | None, rr: float | None, direction: str = "") -> EntryLocationAssessment:
        return EntryLocationAssessment(score, permission, state, tuple(reasons), components, None if swing is None else round(swing, 4), None if extension is None else round(extension, 4), None if rr is None else round(rr, 4), direction)

    def _blocked_invalid(self, reason: str, swing: float | None = None, extension: float | None = None, direction: str = "") -> EntryLocationAssessment:
        return self._assessment(0.0, False, EntryState.BLOCK_INVALID_GEOMETRY, [reason], {}, swing, extension, None, direction)
