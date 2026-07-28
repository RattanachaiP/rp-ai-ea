"""Target feasibility independent from reward/risk policy."""
from .stop_feasibility import Feasibility

def validate_take_profit(*, entry_price, target, direction, minimum_distance):
    if target is None: return Feasibility("DEFERRED", ("TARGET_MISSING",))
    distance = target-entry_price if direction == "BUY" else entry_price-target
    reasons = []
    if distance <= 0: reasons.append("TARGET_WRONG_SIDE")
    if distance < minimum_distance: reasons.append("TARGET_NOT_ACHIEVABLE")
    return Feasibility("INVALID" if reasons else "VALID", tuple(reasons) or ("TARGET_VALID",))
