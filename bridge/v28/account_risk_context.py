"""Immutable account-state input and fail-closed account risk assessment."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class AccountState:
    equity: float
    free_margin: float
    open_exposure: float
    daily_realized_loss: float
    current_drawdown: float
    trading_enabled: bool
    as_of: str

    def __post_init__(self):
        values = (self.equity, self.free_margin, self.open_exposure, self.daily_realized_loss,
                  self.current_drawdown)
        if any(type(v) not in (int, float) or not isfinite(v) or v < 0 for v in values) or not self.as_of:
            raise ValueError("ACCOUNT_STATE_INVALID")


@dataclass(frozen=True)
class AccountRiskPolicy:
    maximum_exposure: float
    daily_loss_limit: float
    drawdown_limit: float
    minimum_free_margin: float
    risk_fraction: float
    capital_fraction: float


@dataclass(frozen=True)
class AccountRiskAssessment:
    status: str
    reasons: tuple[str, ...]
    remaining_daily_budget: float
    exposure_available: float


def assess_account_risk(account: AccountState, policy: AccountRiskPolicy) -> AccountRiskAssessment:
    reasons = []
    if not account.trading_enabled: reasons.append("ACCOUNT_TRADING_DISABLED")
    if account.open_exposure >= policy.maximum_exposure: reasons.append("MAXIMUM_EXPOSURE_REACHED")
    if account.daily_realized_loss >= policy.daily_loss_limit: reasons.append("DAILY_LOSS_GUARD_REACHED")
    if account.current_drawdown >= policy.drawdown_limit: reasons.append("DRAWDOWN_ALLOWANCE_REACHED")
    if account.free_margin < policy.minimum_free_margin: reasons.append("MARGIN_UNAVAILABLE")
    return AccountRiskAssessment("INVALID" if reasons else "VALID", tuple(reasons) or ("ACCOUNT_RISK_VALID",),
        max(0.0, policy.daily_loss_limit-account.daily_realized_loss),
        max(0.0, policy.maximum_exposure-account.open_exposure))
