"""Governed, immutable policy for PR266 operational qualification."""
from dataclasses import dataclass
from typing import Any
from .pipeline_validator import certification_identity

POLICY_VERSION = "1.0.0"

@dataclass(frozen=True)
class QualificationPolicy:
    policy_name: str
    policy_version: str
    minimum_campaign_duration_seconds: float
    minimum_run_count: int
    minimum_runs_per_action: int
    minimum_evidence_density_per_hour: float
    maximum_heartbeat_gap_seconds: float
    require_strict_runtime_sequence: bool
    maximum_delivery_failure_rate: float
    required_consecutive_stable_campaigns: int
    expiry_after_seconds: float
    recommendation_transitions: tuple[tuple[str, str], ...]
    policy_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "policy_identity"}

    def __post_init__(self):
        if self.policy_version != POLICY_VERSION or not self.policy_name:
            raise ValueError("QUALIFICATION_POLICY_VERSION_INVALID")
        positive = (self.minimum_campaign_duration_seconds, self.minimum_run_count,
                    self.minimum_runs_per_action, self.minimum_evidence_density_per_hour,
                    self.maximum_heartbeat_gap_seconds,
                    self.required_consecutive_stable_campaigns, self.expiry_after_seconds)
        if any(type(x) not in (int, float) or x <= 0 for x in positive):
            raise ValueError("QUALIFICATION_POLICY_THRESHOLD_INVALID")
        if type(self.require_strict_runtime_sequence) is not bool or not 0 <= self.maximum_delivery_failure_rate <= 1:
            raise ValueError("QUALIFICATION_POLICY_THRESHOLD_INVALID")
        expected = (("FAIL", "NOT READY"), ("INCOMPLETE", "CONDITIONALLY READY"),
                    ("PASS", "READY FOR HUMAN REVIEW"))
        if self.recommendation_transitions != expected:
            raise ValueError("QUALIFICATION_POLICY_RECOMMENDATIONS_INVALID")
        if self.policy_identity != certification_identity("V28_QUALIFICATION_POLICY", self.canonical_payload()):
            raise ValueError("QUALIFICATION_POLICY_IDENTITY_INVALID")

    def recommendation(self, state: str) -> str:
        try: return dict(self.recommendation_transitions)[state]
        except KeyError as error: raise ValueError("QUALIFICATION_STATE_INVALID") from error


def create_qualification_policy(**overrides: Any) -> QualificationPolicy:
    values = dict(policy_name="V28_OPERATIONAL_QUALIFICATION_POLICY", policy_version=POLICY_VERSION,
        minimum_campaign_duration_seconds=3600.0, minimum_run_count=15,
        minimum_runs_per_action=5, minimum_evidence_density_per_hour=12.0,
        maximum_heartbeat_gap_seconds=300.0,
        require_strict_runtime_sequence=True, maximum_delivery_failure_rate=0.0,
        required_consecutive_stable_campaigns=1, expiry_after_seconds=86400.0,
        recommendation_transitions=(("FAIL", "NOT READY"), ("INCOMPLETE", "CONDITIONALLY READY"),
                                    ("PASS", "READY FOR HUMAN REVIEW")))
    values.update(overrides)
    return QualificationPolicy(**values, policy_identity=certification_identity("V28_QUALIFICATION_POLICY", values))

DEFAULT_QUALIFICATION_POLICY = create_qualification_policy()
