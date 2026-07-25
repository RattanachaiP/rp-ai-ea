"""Immutable policy for PR180 advisory package preparation."""
from dataclasses import dataclass
from .identity import digest, policy_uuid

@dataclass(frozen=True)
class RuntimeKnowledgePackagingPolicy:
    runtime_packaging_policy_version: str = "PR180-PACKAGING-POLICY.1.0"
    required_registry_state: str = "ADVISORY_ENTRY_RECORDED"
    required_advisory_only: bool = True
    required_registry_engine_version: str | None = None
    required_registry_admission_policy_version: str | None = None
    required_promotion_engine_version: str | None = None
    required_promotion_policy_version: str | None = None
    require_snapshot_membership: bool = True
    require_complete_provenance: bool = True

    def __post_init__(self):
        if (not isinstance(self.runtime_packaging_policy_version, str)
                or not self.runtime_packaging_policy_version
                or self.required_registry_state != "ADVISORY_ENTRY_RECORDED"
                or self.required_advisory_only is not True
                or self.require_snapshot_membership is not True
                or self.require_complete_provenance is not True
                or any(value is not None and (not isinstance(value, str) or not value)
                       for value in (self.required_registry_engine_version,
                                     self.required_registry_admission_policy_version,
                                     self.required_promotion_engine_version,
                                     self.required_promotion_policy_version))):
            raise ValueError("INVALID_RUNTIME_PACKAGING_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def runtime_packaging_policy_uuid(self):
        return policy_uuid(self.to_dict())

    @property
    def runtime_packaging_policy_digest(self):
        return digest(self.to_dict())
