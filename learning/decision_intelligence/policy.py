"""Immutable policy for preparing advisory decision intelligence."""

from dataclasses import dataclass
from .identity import digest, policy_uuid


@dataclass(frozen=True)
class DecisionIntelligencePolicy:
    intelligence_policy_version: str = "PR184-INTELLIGENCE-POLICY.1.0"
    intelligence_engine_version: str = "PR184.1.0"
    prepared_context_state: str = "CONTEXT_PREPARED"
    insufficient_context_state: str = "INSUFFICIENT_CONTEXT_EVIDENCE"

    def __post_init__(self):
        if (self.intelligence_engine_version != "PR184.1.0" or
                self.prepared_context_state != "CONTEXT_PREPARED" or
                self.insufficient_context_state != "INSUFFICIENT_CONTEXT_EVIDENCE"):
            raise ValueError("INVALID_INTELLIGENCE_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def intelligence_policy_digest(self): return digest(self.to_dict())

    @property
    def intelligence_policy_uuid(self): return policy_uuid(self.to_dict())
