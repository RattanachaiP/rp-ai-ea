"""Immutable portfolio exposure context and concentration validation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioExposure:
    symbol_exposure: float
    directional_exposure: float
    overlapping_exposure: float
    correlated_exposure: float

@dataclass(frozen=True)
class PortfolioPolicy:
    maximum_symbol_exposure: float
    maximum_directional_exposure: float
    maximum_overlap: float
    maximum_correlated_exposure: float

def assess_portfolio(exposure, policy, proposed):
    reasons=[]
    if exposure.symbol_exposure+proposed > policy.maximum_symbol_exposure: reasons.append("SYMBOL_CONCENTRATION")
    if exposure.directional_exposure+proposed > policy.maximum_directional_exposure: reasons.append("DIRECTIONAL_CONCENTRATION")
    if exposure.overlapping_exposure+proposed > policy.maximum_overlap: reasons.append("PORTFOLIO_OVERLAP")
    if exposure.correlated_exposure+proposed > policy.maximum_correlated_exposure: reasons.append("CORRELATION_ALLOWANCE")
    return ("INVALID" if reasons else "VALID", tuple(reasons) or ("PORTFOLIO_EXPOSURE_VALID",))
