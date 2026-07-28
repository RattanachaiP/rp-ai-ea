"""Governed expected reward/risk calculation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RewardRisk:
    expected_reward: float
    expected_risk: float
    reward_risk_ratio: float
    execution_viability: str
    reasons: tuple[str, ...]

def validate_reward_risk(*, entry_price, stop, target, minimum_ratio):
    if stop is None or target is None:
        return RewardRisk(0, 0, 0, "DEFERRED", ("REWARD_RISK_INPUT_MISSING",))
    risk, reward = abs(entry_price-stop), abs(target-entry_price)
    ratio = reward/risk if risk > 0 else 0
    valid = risk > 0 and ratio >= minimum_ratio
    return RewardRisk(reward, risk, ratio, "VALID" if valid else "INVALID",
                      ("REWARD_RISK_VALID",) if valid else ("MINIMUM_REWARD_RISK_FAILED",))
