"""Immutable PR186 advisory readiness policy."""

from dataclasses import dataclass
from .identity import digest, policy_uuid


POLICY_VERSION = "PR186-EXECUTION_READINESS-POLICY.1.0"
ENGINE_VERSION = "PR186.1.0"


@dataclass(frozen=True)
class ExecutionReadinessPolicy:
    readiness_policy_version: str = POLICY_VERSION
    readiness_engine_version: str = ENGINE_VERSION
    ready_recommendation_state: str = "RECOMMENDATION_READY"
    insufficient_recommendation_state: str = "INSUFFICIENT_RECOMMENDATION_EVIDENCE"

    def __post_init__(self):
        if (
            self.readiness_policy_version != POLICY_VERSION
            or self.readiness_engine_version != ENGINE_VERSION
            or self.ready_recommendation_state != "RECOMMENDATION_READY"
            or self.insufficient_recommendation_state
            != "INSUFFICIENT_RECOMMENDATION_EVIDENCE"
        ):
            raise ValueError("INVALID_EXECUTION_READINESS_POLICY")

    def to_dict(self):
        return {n: getattr(self, n) for n in self.__dataclass_fields__}

    @property
    def readiness_policy_digest(self):
        return digest(self.to_dict())

    @property
    def readiness_policy_uuid(self):
        return policy_uuid(self.to_dict())
