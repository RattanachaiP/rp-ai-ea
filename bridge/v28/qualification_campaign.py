"""Immutable PR266 long-duration qualification campaign contracts."""
from dataclasses import dataclass
from typing import Any, Iterable

from .execution_plan import parse_utc
from .pipeline_validator import certification_identity, report_identity_valid
from .certification_report import CertificationReport

PR266_POLICY = "V28_OPERATIONAL_QUALIFICATION_POLICY@1.0.0"
ACTIONS = ("BUY", "SELL", "HOLD")

@dataclass(frozen=True)
class QualificationRun:
    ordinal: int
    action: str
    observed_at: str
    certification: CertificationReport
    runtime_health_identity: str
    publication_succeeded: bool
    validation_succeeded: bool
    delivery_succeeded: bool
    recovery_attempted: bool
    replay_identity: str

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}

    def __post_init__(self):
        parse_utc(self.observed_at)
        if type(self.ordinal) is not int or self.ordinal < 1 or self.action not in ACTIONS:
            raise ValueError("QUALIFICATION_RUN_INVALID")
        if not report_identity_valid(self.certification, CertificationReport, "V28_END_TO_END_CERTIFICATION"):
            raise ValueError("QUALIFICATION_CERTIFICATION_INVALID")
        for name in ("publication_succeeded", "validation_succeeded", "delivery_succeeded", "recovery_attempted"):
            if type(getattr(self, name)) is not bool:
                raise ValueError("QUALIFICATION_RUN_INVALID")
        if not self.runtime_health_identity:
            raise ValueError("QUALIFICATION_RUNTIME_HEALTH_MISSING")
        if self.replay_identity != certification_identity("V28_QUALIFICATION_RUN", self.canonical_payload()):
            raise ValueError("QUALIFICATION_RUN_REPLAY_INVALID")


def create_qualification_run(**values: Any) -> QualificationRun:
    return QualificationRun(**values, replay_identity=certification_identity("V28_QUALIFICATION_RUN", values))

@dataclass(frozen=True)
class QualificationCampaign:
    campaign_identity: str
    lineage_identity: str | None
    started_at: str
    expires_at: str
    runs: tuple[QualificationRun, ...]
    policy_reference: str
    production_authorized: bool

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "campaign_identity"}

    def __post_init__(self):
        started, expires = parse_utc(self.started_at), parse_utc(self.expires_at)
        if expires <= started or self.policy_reference != PR266_POLICY or self.production_authorized is not False:
            raise ValueError("QUALIFICATION_CAMPAIGN_INVALID")
        if not self.runs or tuple(x.ordinal for x in self.runs) != tuple(range(1, len(self.runs) + 1)):
            raise ValueError("QUALIFICATION_CAMPAIGN_SEQUENCE_INVALID")
        if any(type(x) is not QualificationRun for x in self.runs):
            raise ValueError("QUALIFICATION_CAMPAIGN_RUN_INVALID")
        times = tuple(parse_utc(x.observed_at) for x in self.runs)
        if tuple(sorted(times)) != times or any(x < started or x >= expires for x in times):
            raise ValueError("QUALIFICATION_CAMPAIGN_TIME_INVALID")
        if self.campaign_identity != certification_identity("V28_QUALIFICATION_CAMPAIGN", self.canonical_payload()):
            raise ValueError("QUALIFICATION_CAMPAIGN_IDENTITY_INVALID")

    def is_expired(self, at: str) -> bool:
        return parse_utc(at) >= parse_utc(self.expires_at)


def create_qualification_campaign(*, lineage_identity: str | None, started_at: str,
                                  expires_at: str, runs: Iterable[QualificationRun]) -> QualificationCampaign:
    values = dict(lineage_identity=lineage_identity, started_at=started_at, expires_at=expires_at,
                  runs=tuple(runs), policy_reference=PR266_POLICY, production_authorized=False)
    return QualificationCampaign(campaign_identity=certification_identity("V28_QUALIFICATION_CAMPAIGN", values), **values)
