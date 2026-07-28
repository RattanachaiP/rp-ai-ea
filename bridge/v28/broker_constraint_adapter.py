"""Pure validation adapter for broker constraints; it never submits orders."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BrokerConstraints:
    minimum_volume: float
    maximum_volume: float
    volume_step: float
    stop_level: float
    freeze_level: float
    margin_per_volume: float
    trading_session_open: bool
    symbol_available: bool
    as_of: str


@dataclass(frozen=True)
class BrokerAssessment:
    status: str
    reasons: tuple[str, ...]


def validate_broker_constraints(constraints: BrokerConstraints, *, volume: float, stop_distance: float,
                                target_distance: float, free_margin: float) -> BrokerAssessment:
    reasons = []
    if not constraints.symbol_available: reasons.append("SYMBOL_UNAVAILABLE")
    if not constraints.trading_session_open: reasons.append("TRADING_SESSION_CLOSED")
    if not constraints.minimum_volume <= volume <= constraints.maximum_volume: reasons.append("VOLUME_OUT_OF_RANGE")
    if constraints.volume_step <= 0 or Decimal(str(volume)) % Decimal(str(constraints.volume_step)) != 0:
        reasons.append("VOLUME_STEP_INVALID")
    if min(stop_distance, target_distance) < constraints.stop_level: reasons.append("STOP_LEVEL_VIOLATION")
    if min(stop_distance, target_distance) <= constraints.freeze_level: reasons.append("FREEZE_LEVEL_VIOLATION")
    if volume * constraints.margin_per_volume > free_margin: reasons.append("BROKER_MARGIN_INSUFFICIENT")
    return BrokerAssessment("INVALID" if reasons else "VALID", tuple(reasons) or ("BROKER_CONSTRAINTS_VALID",))
