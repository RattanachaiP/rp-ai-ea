"""Immutable, explicitly declared PR187 environment evaluation policy."""

from dataclasses import dataclass
from math import isfinite
from .identity import digest, policy_uuid

POLICY_VERSION = "PR187-EXECUTION-ENVIRONMENT-POLICY.2.0"
ENGINE_VERSION = "PR187.2.0"
ENVIRONMENT_DIMENSIONS = (
    "feed_stability",
    "price_stream_continuity",
    "market_session_quality",
    "spread_quality",
    "latency_quality",
    "slippage_expectation",
    "market_liquidity_quality",
    "environment_consistency",
    "data_freshness",
    "environment_completeness",
)


@dataclass(frozen=True)
class ExecutionEnvironmentPolicy:
    environment_policy_version: str = POLICY_VERSION
    environment_engine_version: str = ENGINE_VERSION
    minimum_quality: float = 0.8
    minimum_feed_stability: float = 0.95
    minimum_price_stream_continuity: float = 0.99
    minimum_market_session_quality: float = 0.8
    maximum_spread_points: float = 50.0
    maximum_latency_ms: float = 250.0
    maximum_slippage_points: float = 30.0
    minimum_market_liquidity_quality: float = 0.8
    minimum_environment_consistency: float = 0.8
    maximum_data_age_seconds: float = 5.0
    minimum_environment_completeness: float = 0.9

    def __post_init__(self):
        values = tuple(
            getattr(self, n)
            for n in self.__dataclass_fields__
            if n not in {"environment_policy_version", "environment_engine_version"}
        )
        if (
            not isinstance(self.environment_policy_version, str)
            or not self.environment_policy_version.strip()
            or not isinstance(self.environment_engine_version, str)
            or not self.environment_engine_version.strip()
            or any(type(v) is not float or not isfinite(v) or v < 0 for v in values)
            or not 0.0 <= self.minimum_quality <= 1.0
        ):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_POLICY")

    def to_dict(self):
        return {n: getattr(self, n) for n in self.__dataclass_fields__}

    @property
    def environment_policy_digest(self):
        return digest(self.to_dict())

    @property
    def environment_policy_uuid(self):
        return policy_uuid(self.to_dict())

    def available(self, dimension, value):
        tests = {
            "feed_stability": value >= self.minimum_feed_stability,
            "price_stream_continuity": value >= self.minimum_price_stream_continuity,
            "market_session_quality": value >= self.minimum_market_session_quality,
            "spread_quality": value <= self.maximum_spread_points,
            "latency_quality": value <= self.maximum_latency_ms,
            "slippage_expectation": value <= self.maximum_slippage_points,
            "market_liquidity_quality": value >= self.minimum_market_liquidity_quality,
            "environment_consistency": value >= self.minimum_environment_consistency,
            "data_freshness": value <= self.maximum_data_age_seconds,
            "environment_completeness": value >= self.minimum_environment_completeness,
        }
        return tests[dimension]
