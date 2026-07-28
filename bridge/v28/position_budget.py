"""Dimensionally correct account-currency position budget construction."""
from dataclasses import dataclass
from .broker_constraint_adapter import floor_volume
from .execution_plan import _finite

@dataclass(frozen=True)
class PositionBudget:
    risk_budget_account_currency: float; capital_allocation_account_currency: float
    available_exposure_account_currency: float; monetary_risk_per_volume: float
    margin_required_per_volume: float; risk_based_volume: float; margin_based_volume: float
    exposure_based_volume: float; approved_volume: float; status: str
    def __post_init__(self):
        for k,v in self.__dict__.items():
            if k not in {"status"}: _finite(v,nonnegative=True)
        if self.status not in {"VALID","INVALID"} or (self.status=="VALID" and self.approved_volume<=0): raise ValueError("POSITION_BUDGET_INVALID")

def construct_position_budget(account,policy,assessment,spec,*,monetary_risk_per_volume,notional_per_volume,available_exposure_account_currency,requested_cap=None):
    risk_budget=min(account.equity_account_currency*policy.risk_fraction_of_equity,assessment.remaining_daily_loss_budget_amount)
    capital=min(account.free_margin_account_currency,account.equity_account_currency*policy.capital_fraction_of_equity)
    risk_volume=risk_budget/monetary_risk_per_volume
    margin_volume=capital/spec.margin_required_per_volume
    exposure_volume=max(0,available_exposure_account_currency)/notional_per_volume
    candidates=[risk_volume,margin_volume,exposure_volume,spec.maximum_volume]
    if requested_cap is not None: candidates.append(requested_cap)
    approved=floor_volume(min(candidates),spec)
    if approved<spec.minimum_volume: approved=0
    return PositionBudget(risk_budget,capital,available_exposure_account_currency,monetary_risk_per_volume,spec.margin_required_per_volume,risk_volume,margin_volume,exposure_volume,approved,"VALID" if assessment.status=="VALID" and approved>0 else "INVALID")
