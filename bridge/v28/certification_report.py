"""Canonical aggregate PR265 certification report and JSON rendering."""
from dataclasses import dataclass
import json
from typing import Any, Mapping
from .pipeline_validator import PR265_POLICY, PipelineValidationReport, certification_identity
from .replay_consistency_checker import ReplayConsistencyReport
from .runtime_certifier import RuntimeCertification
from .shadow_validation_runner import ShadowValidationReport
from .operational_readiness import OperationalReadinessReport

def _plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"): return {k: _plain(getattr(value, k)) for k in value.__dataclass_fields__}
    if isinstance(value, Mapping): return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value

@dataclass(frozen=True)
class CertificationReport:
    status: str; architecture: PipelineValidationReport; replay: ReplayConsistencyReport
    shadow: ShadowValidationReport; runtime: RuntimeCertification; readiness: OperationalReadinessReport
    policy_reference: str; production_authorized: bool; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def to_json(self) -> str: return json.dumps(_plain(self), sort_keys=True, separators=(",", ":"), allow_nan=False)
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.production_authorized is not False: raise ValueError("CERTIFICATION_REPORT_INVALID")
        if self.replay_identity != certification_identity("V28_END_TO_END_CERTIFICATION", self.canonical_payload()): raise ValueError("CERTIFICATION_REPORT_REPLAY_INVALID")

def build_certification_report(architecture: PipelineValidationReport, replay: ReplayConsistencyReport,
                               shadow: ShadowValidationReport, runtime: RuntimeCertification,
                               readiness: OperationalReadinessReport) -> CertificationReport:
    reports = (architecture, replay, shadow, runtime, readiness)
    status = "PASS" if all(report.status == "PASS" for report in reports) else "FAIL"
    values = dict(status=status, architecture=architecture, replay=replay, shadow=shadow, runtime=runtime,
                  readiness=readiness, policy_reference=PR265_POLICY, production_authorized=False)
    return CertificationReport(**values, replay_identity=certification_identity("V28_END_TO_END_CERTIFICATION", values))
