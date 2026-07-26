"""Immutable PR188 feasibility policy."""

from dataclasses import dataclass
from .identity import digest, policy_uuid

POLICY_VERSION = "PR188-EXECUTION-FEASIBILITY-POLICY.1.0"
ENGINE_VERSION = "PR188.1.0"
FEASIBILITY_DIMENSIONS = (
    "internal_governance_completeness",
    "execution_readiness",
    "execution_environment_quality",
    "repository_integrity",
    "policy_continuity",
    "snapshot_continuity",
    "historical_lineage_continuity",
    "replay_continuity",
)


@dataclass(frozen=True)
class ExecutionFeasibilityPolicy:
    feasibility_policy_version: str = POLICY_VERSION
    feasibility_engine_version: str = ENGINE_VERSION

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in (
            self.feasibility_policy_version, self.feasibility_engine_version
        )):
            raise ValueError("INVALID_EXECUTION_FEASIBILITY_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def feasibility_policy_digest(self):
        return digest(self.to_dict())

    @property
    def feasibility_policy_uuid(self):
        return policy_uuid(self.to_dict())
