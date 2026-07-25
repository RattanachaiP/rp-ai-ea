"""Immutable PR179 admission policy and neutral assessment outcomes."""
from dataclasses import dataclass
from .identity import digest, registry_policy_uuid

@dataclass(frozen=True)
class RegistryAdmissionPolicy:
    registry_admission_policy_version: str = "PR179-ADMISSION-POLICY.1.0"
    accepted_promotion_state: str = "POLICY_CRITERIA_MET"
    required_advisory_only: bool = True
    required_memory_state: str = "STORED"
    required_threshold_monotonicity_result: str = "PASSED"
    required_promotion_engine_version: str | None = None
    required_promotion_policy_version: str | None = None

    def __post_init__(self):
        if (not isinstance(self.registry_admission_policy_version, str) or not self.registry_admission_policy_version
                or self.accepted_promotion_state != "POLICY_CRITERIA_MET"
                or self.required_advisory_only is not True or self.required_memory_state != "STORED"
                or self.required_threshold_monotonicity_result != "PASSED"
                or any(x is not None and (not isinstance(x, str) or not x) for x in
                       (self.required_promotion_engine_version, self.required_promotion_policy_version))):
            raise ValueError("INVALID_REGISTRY_ADMISSION_POLICY")
    def to_dict(self): return {name: getattr(self, name) for name in self.__dataclass_fields__}
    @property
    def registry_admission_policy_uuid(self): return registry_policy_uuid(self.to_dict())
    @property
    def registry_admission_policy_digest(self): return digest(self.to_dict())

    def assess(self, record):
        if record.promotion_state == "REJECTED":
            return "REJECTED", ("PR178_PROMOTION_REJECTED", "PR179_ADMISSION_REJECTED")
        if record.promotion_state == "INSUFFICIENT_PROMOTION_EVIDENCE":
            return "NOT_ADMITTED", ("PR178_PROMOTION_EVIDENCE_INSUFFICIENT", "PR179_ADMISSION_NOT_RECORDED")
        checks = (record.advisory_only is self.required_advisory_only,
                  record.memory_state == self.required_memory_state,
                  record.threshold_monotonicity_result == self.required_threshold_monotonicity_result,
                  self.required_promotion_engine_version in (None, record.promotion_engine_version),
                  self.required_promotion_policy_version in (None, record.promotion_policy_version))
        if not all(checks):
            return "NOT_ADMITTED", ("PR179_ADMISSION_POLICY_NOT_SATISFIED", "PR179_ADMISSION_NOT_RECORDED")
        return "ADVISORY_ENTRY_RECORDED", ("PR178_POLICY_CRITERIA_CONFIRMED",
            "PR179_ADMISSION_POLICY_PASSED", "ADVISORY_GOVERNANCE_ENTRY_RECORDED")
