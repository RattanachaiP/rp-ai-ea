"""Governed, exact-type operational-readiness aggregation."""
from dataclasses import dataclass
from typing import Any
from .delivery_pipeline_validator import DeliveryValidationReport
from .pipeline_validator import Campaign,PR265_POLICY,PipelineValidationReport,certification_identity,report_identity_valid
from .replay_consistency_checker import ReplayConsistencyReport
from .runtime_certifier import RuntimeCertification
from .shadow_validation_runner import ShadowValidationReport

MANDATORY=((PipelineValidationReport,"V28_PIPELINE_VALIDATION"),(ReplayConsistencyReport,"V28_REPLAY_CONSISTENCY"),(ShadowValidationReport,"V28_SHADOW_VALIDATION"),(DeliveryValidationReport,"V28_DELIVERY_VALIDATION"),(RuntimeCertification,"V28_RUNTIME_CERTIFICATION"))
@dataclass(frozen=True)
class OperationalReadinessReport:
    status:str;campaign:Campaign;evidence_identities:tuple[str,...];failures:tuple[str,...]
    production_authorized:bool;authority_statement:str;policy_reference:str;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.production_authorized is not False or self.authority_statement!="V27_REMAINS_SOLE_PRODUCTION_AUTHORITY":raise ValueError("READINESS_INVALID")
        if self.replay_identity!=certification_identity("V28_OPERATIONAL_READINESS",self.canonical_payload()):raise ValueError("READINESS_REPLAY_INVALID")

def assess_operational_readiness(*reports:Any)->OperationalReadinessReport:
    failures=[]; by_type={}
    for report in reports:
        t=type(report)
        if t not in {x[0] for x in MANDATORY}:failures.append("UNSUPPORTED_REPORT_TYPE");continue
        if t in by_type:failures.append(f"DUPLICATE_{t.__name__.upper()}")
        by_type[t]=report
    for t,domain in MANDATORY:
        if t not in by_type:failures.append(f"MISSING_{t.__name__.upper()}")
        elif not report_identity_valid(by_type[t],t,domain):failures.append(f"FORGED_{t.__name__.upper()}")
    campaigns=[x.campaign for x in by_type.values() if hasattr(x,"campaign")]
    campaign=campaigns[0] if campaigns else None
    if not campaign or any(x!=campaign for x in campaigns):failures.append("CROSS_REPORT_CAMPAIGN_MISMATCH")
    identities=[getattr(x,"replay_identity","") for x in by_type.values()]
    if len(identities)!=len(set(identities)):failures.append("DUPLICATE_REPORT_REPLAY_IDENTITY")
    for report in by_type.values():
        if getattr(report,"policy_reference",None)!=PR265_POLICY:failures.append("REPORT_POLICY_MISMATCH")
        if getattr(report,"status",None)!="PASS":failures.append(f"{type(report).__name__.upper()}_NOT_PASS")
    if campaign is None:
        from .pipeline_validator import create_campaign
        campaign=create_campaign(runtime_sequence_id=-1,symbol="INVALID",evaluation_time="1970-01-01T00:00:00Z",decision_replay_identity="INVALID",plan_replay_identity="INVALID",publication_replay_identity="INVALID",environment_identity="INVALID")
    values=dict(status="FAIL" if failures else "PASS",campaign=campaign,evidence_identities=tuple(identities),failures=tuple(dict.fromkeys(failures)),production_authorized=False,authority_statement="V27_REMAINS_SOLE_PRODUCTION_AUTHORITY",policy_reference=PR265_POLICY)
    return OperationalReadinessReport(**values,replay_identity=certification_identity("V28_OPERATIONAL_READINESS",values))
