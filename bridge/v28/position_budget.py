"""Deterministic position budget construction without broker authority."""
from dataclasses import dataclass
from .account_risk_context import AccountRiskAssessment, AccountRiskPolicy, AccountState


@dataclass(frozen=True)
class PositionBudget:
    maximum_position_size: float
    available_exposure: float
    risk_allocation: float
    capital_allocation: float
    daily_remaining_budget: float
    status: str


def construct_position_budget(account: AccountState, policy: AccountRiskPolicy,
                              assessment: AccountRiskAssessment, *, risk_per_volume: float) -> PositionBudget:
    if risk_per_volume <= 0 or assessment.status != "VALID":
        return PositionBudget(0, assessment.exposure_available, 0, 0, assessment.remaining_daily_budget, "INVALID")
    risk = min(account.equity*policy.risk_fraction, assessment.remaining_daily_budget)
    capital = min(account.free_margin, account.equity*policy.capital_fraction)
    maximum = min(risk/risk_per_volume, assessment.exposure_available, capital/risk_per_volume)
    return PositionBudget(maximum, assessment.exposure_available, risk, capital,
                          assessment.remaining_daily_budget, "VALID" if maximum > 0 else "INVALID")
