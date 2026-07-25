"""Immutable PR187 advisory execution-environment policy."""

from dataclasses import dataclass
from .identity import digest, policy_uuid

POLICY_VERSION = "PR187-EXECUTION-ENVIRONMENT-POLICY.1.0"
ENGINE_VERSION = "PR187.1.0"
ENVIRONMENT_DIMENSIONS = (
    "feed_stability", "price_stream_continuity", "market_session_quality",
    "spread_quality", "latency_quality", "slippage_expectation",
    "market_liquidity_quality", "environment_consistency", "data_freshness",
    "environment_completeness",
)

@dataclass(frozen=True)
class ExecutionEnvironmentPolicy:
    environment_policy_version: str = POLICY_VERSION
    environment_engine_version: str = ENGINE_VERSION
    dimensions: tuple[str, ...] = ENVIRONMENT_DIMENSIONS
    minimum_quality: float = 1.0

    def __post_init__(self):
        object.__setattr__(self, "dimensions", tuple(self.dimensions))
        if (self.environment_policy_version != POLICY_VERSION
            or self.environment_engine_version != ENGINE_VERSION
            or self.dimensions != ENVIRONMENT_DIMENSIONS
            or self.minimum_quality != 1.0):
            raise ValueError("INVALID_EXECUTION_ENVIRONMENT_POLICY")

    def to_dict(self):
        return {"environment_policy_version": self.environment_policy_version,
                "environment_engine_version": self.environment_engine_version,
                "dimensions": list(self.dimensions), "minimum_quality": self.minimum_quality}

    @property
    def environment_policy_digest(self): return digest(self.to_dict())
    @property
    def environment_policy_uuid(self): return policy_uuid(self.to_dict())
