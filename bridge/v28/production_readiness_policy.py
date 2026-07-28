"""Immutable policy contract for governed production-readiness review."""
from dataclasses import dataclass
from typing import Any

from .pipeline_validator import certification_identity

POLICY_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProductionReadinessPolicy:
    policy_name: str
    policy_version: str
    minimum_qualified_campaigns: int
    minimum_stable_campaigns: int
    minimum_runtime_duration_seconds: float
    maximum_failure_rate: float
    maximum_recovery_rate: float
    minimum_evidence_density_per_hour: float
    required_qualification_version: str
    required_architecture_version: str
    policy_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "policy_identity"}

    def __post_init__(self):
        if not self.policy_name or self.policy_version != POLICY_VERSION:
            raise ValueError("READINESS_POLICY_VERSION_INVALID")
        if (type(self.minimum_qualified_campaigns) is not int or self.minimum_qualified_campaigns < 1 or
                type(self.minimum_stable_campaigns) is not int or self.minimum_stable_campaigns < 1 or
                self.minimum_stable_campaigns > self.minimum_qualified_campaigns):
            raise ValueError("READINESS_POLICY_CAMPAIGN_THRESHOLD_INVALID")
        if (type(self.minimum_runtime_duration_seconds) not in (int, float) or
                self.minimum_runtime_duration_seconds <= 0 or
                type(self.minimum_evidence_density_per_hour) not in (int, float) or
                self.minimum_evidence_density_per_hour <= 0):
            raise ValueError("READINESS_POLICY_EVIDENCE_THRESHOLD_INVALID")
        if any(type(value) not in (int, float) or not 0 <= value <= 1
               for value in (self.maximum_failure_rate, self.maximum_recovery_rate)):
            raise ValueError("READINESS_POLICY_RATE_INVALID")
        if not self.required_qualification_version or not self.required_architecture_version:
            raise ValueError("READINESS_POLICY_REQUIRED_VERSION_INVALID")
        if self.policy_identity != certification_identity("V28_PRODUCTION_READINESS_POLICY", self.canonical_payload()):
            raise ValueError("READINESS_POLICY_IDENTITY_INVALID")


def create_production_readiness_policy(**overrides: Any) -> ProductionReadinessPolicy:
    values = dict(policy_name="V28_PRODUCTION_READINESS_POLICY", policy_version=POLICY_VERSION,
                  minimum_qualified_campaigns=3, minimum_stable_campaigns=2,
                  minimum_runtime_duration_seconds=10800.0, maximum_failure_rate=0.0,
                  maximum_recovery_rate=0.0, minimum_evidence_density_per_hour=12.0,
                  required_qualification_version="1.0.0", required_architecture_version="V28")
    values.update(overrides)
    return ProductionReadinessPolicy(
        **values, policy_identity=certification_identity("V28_PRODUCTION_READINESS_POLICY", values))


DEFAULT_PRODUCTION_READINESS_POLICY = create_production_readiness_policy()
