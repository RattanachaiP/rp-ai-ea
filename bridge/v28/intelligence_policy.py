"""Sole governed parameter policy for V28 market intelligence."""
from dataclasses import dataclass


@dataclass(frozen=True)
class IntelligencePolicy:
    policy_id: str = "V28_MARKET_INTELLIGENCE_POLICY"
    version: str = "1.0.0"
    owner: str = "V28_MARKET_INTELLIGENCE"
    minimum_bars: int = 6
    structure_prior_window: int = 3
    structure_recent_window: int = 3
    momentum_baseline_window: int = 2
    momentum_recent_window: int = 2
    volatility_baseline_window: int = 3
    volatility_recent_window: int = 2
    liquidity_window: int = 6
    compression_ratio: float = 0.65
    low_level_ratio: float = 0.85
    expansion_ratio: float = 1.25
    high_level_ratio: float = 1.75
    momentum_deceleration_ratio: float = 0.70
    momentum_acceleration_ratio: float = 1.30
    equal_extrema_tolerance_ratio: float = 0.05

    def __post_init__(self) -> None:
        if (self.policy_id != "V28_MARKET_INTELLIGENCE_POLICY" or self.version != "1.0.0"
                or self.owner != "V28_MARKET_INTELLIGENCE"):
            raise ValueError("POLICY_IDENTITY_INVALID")
        integers = (self.minimum_bars, self.structure_prior_window, self.structure_recent_window,
                    self.momentum_baseline_window, self.momentum_recent_window,
                    self.volatility_baseline_window, self.volatility_recent_window, self.liquidity_window)
        if any(type(value) is not int or value < 1 for value in integers):
            raise ValueError("POLICY_WINDOW_INVALID")
        if self.structure_prior_window + self.structure_recent_window > self.minimum_bars:
            raise ValueError("POLICY_STRUCTURE_COHORTS_OVERLAP")
        thresholds = (self.compression_ratio, self.low_level_ratio, self.expansion_ratio,
                      self.high_level_ratio, self.momentum_deceleration_ratio,
                      self.momentum_acceleration_ratio, self.equal_extrema_tolerance_ratio)
        if any(type(value) is not float or value < 0 for value in thresholds):
            raise ValueError("POLICY_THRESHOLD_INVALID")
        if not self.compression_ratio < self.low_level_ratio < 1 < self.expansion_ratio < self.high_level_ratio:
            raise ValueError("POLICY_VOLATILITY_ORDER_INVALID")


DEFAULT_POLICY = IntelligencePolicy()
