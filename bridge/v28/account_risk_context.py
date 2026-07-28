"""Account-currency risk state, policy and assessment contracts."""
from dataclasses import dataclass
from .execution_plan import _finite, identity, parse_utc

@dataclass(frozen=True)
class AccountState:
    equity_account_currency: float; free_margin_account_currency: float
    open_exposure_account_currency: float; daily_realized_loss_amount: float
    current_drawdown_amount: float; trading_enabled: bool; account_currency: str
    as_of: str; source: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        for v in (self.equity_account_currency,self.free_margin_account_currency,self.open_exposure_account_currency,self.daily_realized_loss_amount,self.current_drawdown_amount): _finite(v,nonnegative=True)
        if not self.account_currency or not self.source or type(self.trading_enabled) is not bool: raise ValueError("ACCOUNT_IDENTITY_INVALID")
        parse_utc(self.as_of)
        if self.replay_identity!=identity("V28_ACCOUNT_STATE_REPLAY",self.canonical_payload()): raise ValueError("ACCOUNT_REPLAY_INVALID")

def create_account_state(**values): return AccountState(**values,replay_identity=identity("V28_ACCOUNT_STATE_REPLAY",values))

@dataclass(frozen=True)
class AccountRiskPolicy:
    maximum_exposure_account_currency: float; daily_loss_limit_amount: float
    drawdown_limit_amount: float; minimum_free_margin_account_currency: float
    risk_fraction_of_equity: float; capital_fraction_of_equity: float
    def __post_init__(self):
        for v in (self.maximum_exposure_account_currency,self.daily_loss_limit_amount,self.drawdown_limit_amount,self.minimum_free_margin_account_currency): _finite(v,nonnegative=True)
        for v in (self.risk_fraction_of_equity,self.capital_fraction_of_equity):
            _finite(v,positive=True)
            if v>1: raise ValueError("ACCOUNT_POLICY_FRACTION_INVALID")

@dataclass(frozen=True)
class AccountRiskAssessment:
    status: str; reasons: tuple[str,...]; remaining_daily_loss_budget_amount: float
    available_exposure_account_currency: float
    def __post_init__(self):
        if self.status not in {"VALID","INVALID"} or not self.reasons: raise ValueError("ACCOUNT_ASSESSMENT_INVALID")
        _finite(self.remaining_daily_loss_budget_amount,nonnegative=True); _finite(self.available_exposure_account_currency,nonnegative=True)

def assess_account_risk(account,policy):
    reasons=[]
    if not account.trading_enabled: reasons.append("ACCOUNT_TRADING_DISABLED")
    if account.open_exposure_account_currency>=policy.maximum_exposure_account_currency: reasons.append("MAXIMUM_EXPOSURE_REACHED")
    if account.daily_realized_loss_amount>=policy.daily_loss_limit_amount: reasons.append("DAILY_LOSS_GUARD_REACHED")
    if account.current_drawdown_amount>=policy.drawdown_limit_amount: reasons.append("DRAWDOWN_ALLOWANCE_REACHED")
    if account.free_margin_account_currency<policy.minimum_free_margin_account_currency: reasons.append("MARGIN_UNAVAILABLE")
    return AccountRiskAssessment("INVALID" if reasons else "VALID",tuple(reasons) or ("ACCOUNT_RISK_VALID",),max(0,policy.daily_loss_limit_amount-account.daily_realized_loss_amount),max(0,policy.maximum_exposure_account_currency-account.open_exposure_account_currency))
