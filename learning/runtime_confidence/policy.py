"""Immutable PR182 confidence policy; it grants no decision authority."""
from dataclasses import dataclass
from .identity import digest, policy_uuid

@dataclass(frozen=True)
class RuntimeConfidencePolicy:
    confidence_policy_version: str = "PR182-CONFIDENCE-POLICY.1.0"
    confidence_engine_version: str = "PR182.1.0"
    required_eligibility_state: str = "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"

    def __post_init__(self):
        if (not self.confidence_policy_version or not self.confidence_engine_version
                or self.required_eligibility_state != "ELIGIBLE_FOR_CONFIDENCE_EVALUATION"):
            raise ValueError("INVALID_CONFIDENCE_POLICY")
    def to_dict(self): return {n: getattr(self, n) for n in self.__dataclass_fields__}
    @property
    def confidence_policy_uuid(self): return policy_uuid(self.to_dict())
    @property
    def confidence_policy_digest(self): return digest(self.to_dict())
