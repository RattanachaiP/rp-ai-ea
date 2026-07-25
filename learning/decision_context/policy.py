"""Immutable policy for preparing advisory decision context."""

from dataclasses import dataclass
from .identity import digest, policy_uuid


@dataclass(frozen=True)
class DecisionContextPolicy:
    context_policy_version: str = "PR183-CONTEXT-POLICY.1.0"
    context_engine_version: str = "PR183.1.0"
    prepared_confidence_state: str = "CONFIDENCE_EVALUATED"
    insufficient_confidence_state: str = "INSUFFICIENT_CONFIDENCE_EVIDENCE"

    def __post_init__(self):
        if (self.context_engine_version != "PR183.1.0" or
                self.prepared_confidence_state != "CONFIDENCE_EVALUATED" or
                self.insufficient_confidence_state != "INSUFFICIENT_CONFIDENCE_EVIDENCE"):
            raise ValueError("INVALID_CONTEXT_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def context_policy_digest(self): return digest(self.to_dict())

    @property
    def context_policy_uuid(self): return policy_uuid(self.to_dict())
