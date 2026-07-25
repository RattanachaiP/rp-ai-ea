"""Immutable PR181 eligibility policy; it grants no Runtime authority."""

from dataclasses import dataclass

from .identity import digest, policy_uuid


@dataclass(frozen=True)
class RuntimeKnowledgeSelectionPolicy:
    selection_policy_version: str = "PR181-SELECTION-POLICY.1.0"
    runtime_selector_version: str = "PR181.1.0"
    minimum_package_integrity: str = "ADVISORY_PACKAGE_PREPARED"
    required_registry_state: str = "ADVISORY_ENTRY_RECORDED"
    required_validation_state: str = "STATISTICALLY_CONSISTENT"
    required_promotion_state: str = "POLICY_CRITERIA_MET"

    def __post_init__(self):
        expected = (
            "ADVISORY_PACKAGE_PREPARED",
            "ADVISORY_ENTRY_RECORDED",
            "STATISTICALLY_CONSISTENT",
            "POLICY_CRITERIA_MET",
        )
        actual = (
            self.minimum_package_integrity,
            self.required_registry_state,
            self.required_validation_state,
            self.required_promotion_state,
        )
        if (
            not isinstance(self.selection_policy_version, str)
            or not self.selection_policy_version
            or not isinstance(self.runtime_selector_version, str)
            or not self.runtime_selector_version
            or actual != expected
        ):
            raise ValueError("INVALID_RUNTIME_KNOWLEDGE_SELECTION_POLICY")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def selection_policy_uuid(self):
        return policy_uuid(self.to_dict())

    @property
    def selection_policy_digest(self):
        return digest(self.to_dict())
