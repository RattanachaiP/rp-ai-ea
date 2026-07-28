"""Portfolio exposure measured exclusively in account-currency notional."""
from dataclasses import dataclass
from .execution_plan import _finite

@dataclass(frozen=True)
class PortfolioExposure:
    symbol_exposure_account_currency: float; directional_exposure_account_currency: float
    overlapping_exposure_account_currency: float; correlated_exposure_account_currency: float
    account_currency: str
    def __post_init__(self):
        for v in (self.symbol_exposure_account_currency,self.directional_exposure_account_currency,self.overlapping_exposure_account_currency,self.correlated_exposure_account_currency): _finite(v,nonnegative=True)
        if not self.account_currency: raise ValueError("PORTFOLIO_CURRENCY_INVALID")

@dataclass(frozen=True)
class PortfolioPolicy:
    maximum_symbol_exposure_account_currency: float; maximum_directional_exposure_account_currency: float
    maximum_overlap_account_currency: float; maximum_correlated_exposure_account_currency: float
    def __post_init__(self):
        for v in self.__dict__.values(): _finite(v,nonnegative=True)

def exposure_capacity(exposure,policy):
    return min(policy.maximum_symbol_exposure_account_currency-exposure.symbol_exposure_account_currency,
        policy.maximum_directional_exposure_account_currency-exposure.directional_exposure_account_currency,
        policy.maximum_overlap_account_currency-exposure.overlapping_exposure_account_currency,
        policy.maximum_correlated_exposure_account_currency-exposure.correlated_exposure_account_currency)

def assess_portfolio(exposure,policy,proposed_exposure_account_currency):
    reasons=[]
    pairs=((exposure.symbol_exposure_account_currency,policy.maximum_symbol_exposure_account_currency,"SYMBOL_CONCENTRATION"),(exposure.directional_exposure_account_currency,policy.maximum_directional_exposure_account_currency,"DIRECTIONAL_CONCENTRATION"),(exposure.overlapping_exposure_account_currency,policy.maximum_overlap_account_currency,"PORTFOLIO_OVERLAP"),(exposure.correlated_exposure_account_currency,policy.maximum_correlated_exposure_account_currency,"CORRELATION_ALLOWANCE"))
    for current,limit,reason in pairs:
        if current+proposed_exposure_account_currency>limit: reasons.append(reason)
    return ("INVALID" if reasons else "VALID",tuple(reasons) or ("PORTFOLIO_EXPOSURE_VALID",))
