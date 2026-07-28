"""Integrity-checked aggregate of one exact certification campaign."""
from dataclasses import dataclass
import json
from typing import Any,Mapping
from .delivery_pipeline_validator import DeliveryValidationReport
from .operational_readiness import OperationalReadinessReport
from .pipeline_validator import Campaign,PR265_POLICY,PipelineValidationReport,certification_identity,report_identity_valid
from .replay_consistency_checker import ReplayConsistencyReport
from .runtime_certifier import RuntimeCertification
from .shadow_validation_runner import ShadowValidationReport

def _plain(v:Any)->Any:
    if hasattr(v,"__dataclass_fields__"):return {k:_plain(getattr(v,k)) for k in v.__dataclass_fields__}
    if isinstance(v,Mapping):return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [_plain(x) for x in v]
    return v
@dataclass(frozen=True)
class CertificationReport:
    status:str;campaign:Campaign;architecture:PipelineValidationReport;replay:ReplayConsistencyReport
    shadow:ShadowValidationReport;delivery:DeliveryValidationReport;runtime:RuntimeCertification
    readiness:OperationalReadinessReport;policy_reference:str;production_authorized:bool;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def to_json(self):return json.dumps(_plain(self),sort_keys=True,separators=(",",":"),allow_nan=False)
    def __post_init__(self):
        if self.status not in {"PASS","FAIL"} or self.production_authorized is not False:raise ValueError("CERTIFICATION_REPORT_INVALID")
        if self.replay_identity!=certification_identity("V28_END_TO_END_CERTIFICATION",self.canonical_payload()):raise ValueError("CERTIFICATION_REPORT_REPLAY_INVALID")

def build_certification_report(architecture:PipelineValidationReport,replay:ReplayConsistencyReport,
 shadow:ShadowValidationReport,delivery:DeliveryValidationReport,runtime:RuntimeCertification,
 readiness:OperationalReadinessReport)->CertificationReport:
    specs=((architecture,PipelineValidationReport,"V28_PIPELINE_VALIDATION"),(replay,ReplayConsistencyReport,"V28_REPLAY_CONSISTENCY"),(shadow,ShadowValidationReport,"V28_SHADOW_VALIDATION"),(delivery,DeliveryValidationReport,"V28_DELIVERY_VALIDATION"),(runtime,RuntimeCertification,"V28_RUNTIME_CERTIFICATION"),(readiness,OperationalReadinessReport,"V28_OPERATIONAL_READINESS"))
    if any(not report_identity_valid(r,t,d) for r,t,d in specs):raise ValueError("NESTED_REPORT_INTEGRITY_INVALID")
    if any(r.campaign!=architecture.campaign for r,_,_ in specs):raise ValueError("CROSS_REPORT_CAMPAIGN_MISMATCH")
    if len({r.replay_identity for r,_,_ in specs})!=len(specs):raise ValueError("DUPLICATE_REPORT_IDENTITY")
    if any(r.policy_reference!=PR265_POLICY for r,_,_ in specs):raise ValueError("CROSS_REPORT_POLICY_MISMATCH")
    values=dict(status="PASS" if all(r.status=="PASS" for r,_,_ in specs) else "FAIL",campaign=architecture.campaign,architecture=architecture,replay=replay,shadow=shadow,delivery=delivery,runtime=runtime,readiness=readiness,policy_reference=PR265_POLICY,production_authorized=False)
    return CertificationReport(**values,replay_identity=certification_identity("V28_END_TO_END_CERTIFICATION",values))
