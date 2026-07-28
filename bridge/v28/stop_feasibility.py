"""Protective-stop feasibility independent from trade selection."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Feasibility:
    status: str
    reasons: tuple[str, ...]

def validate_stop(*, entry_price, stop, direction, minimum_distance, volatility_distance,
                  maximum_volatility_multiple=3.0):
    if stop is None: return Feasibility("DEFERRED", ("PROTECTIVE_STOP_MISSING",))
    distance = entry_price-stop if direction == "BUY" else stop-entry_price
    reasons = []
    if distance <= 0: reasons.append("PROTECTIVE_STOP_WRONG_SIDE")
    if distance < minimum_distance: reasons.append("MINIMUM_STOP_DISTANCE_FAILED")
    if volatility_distance <= 0: reasons.append("VOLATILITY_REFERENCE_MISSING")
    elif distance > volatility_distance*maximum_volatility_multiple: reasons.append("VOLATILITY_INCOMPATIBLE")
    return Feasibility("INVALID" if reasons else "VALID", tuple(reasons) or ("PROTECTIVE_STOP_VALID",))
