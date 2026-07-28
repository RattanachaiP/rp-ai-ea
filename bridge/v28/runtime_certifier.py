"""Component-owned certification; WARNING is intentionally not part of the ontology."""
from dataclasses import dataclass
from .delivery_pipeline_validator import DeliveryValidationReport
from .pipeline_validator import Campaign,PR265_POLICY,PipelineValidationReport,certification_identity,report_identity_valid

COMPONENTS=("RUNTIME_FOUNDATION","MARKET_INTELLIGENCE","DECISION_INTELLIGENCE","RISK_CONSTRUCTION","EXECUTION_INTEGRATION","DELIVERY")
@dataclass(frozen=True)
class ComponentCertification:
    component:str;status:str;evidence:tuple[str,...]
    def __post_init__(self):
        if self.component not in COMPONENTS or self.status not in {"PASS","FAIL"} or not self.evidence:raise ValueError("COMPONENT_CERTIFICATION_INVALID")
@dataclass(frozen=True)
class RuntimeCertification:
    status:str;campaign:Campaign;components:tuple[ComponentCertification,...];policy_reference:str
    production_authorized:bool;replay_identity:str
    def canonical_payload(self):return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if tuple(x.component for x in self.components)!=COMPONENTS or self.production_authorized is not False:raise ValueError("RUNTIME_CERTIFICATION_INVALID")
        if self.replay_identity!=certification_identity("V28_RUNTIME_CERTIFICATION",self.canonical_payload()):raise ValueError("RUNTIME_CERTIFICATION_REPLAY_INVALID")

def certify_runtime(pipeline:PipelineValidationReport,delivery:DeliveryValidationReport)->RuntimeCertification:
    if not report_identity_valid(pipeline,PipelineValidationReport,"V28_PIPELINE_VALIDATION"):raise ValueError("PIPELINE_REPORT_INTEGRITY_INVALID")
    if not report_identity_valid(delivery,DeliveryValidationReport,"V28_DELIVERY_VALIDATION"):raise ValueError("DELIVERY_REPORT_INTEGRITY_INVALID")
    if pipeline.campaign!=delivery.campaign:raise ValueError("CERTIFICATION_CAMPAIGN_MISMATCH")
    owned={x.boundary:x for x in pipeline.boundaries}; items=[]
    for name in COMPONENTS:
        evidence=delivery if name=="DELIVERY" else owned.get(name)
        passed=evidence is not None and evidence.status=="PASS"
        items.append(ComponentCertification(name,"PASS" if passed else "FAIL",(getattr(evidence,"replay_identity",name),)))
    values=dict(status="PASS" if all(x.status=="PASS" for x in items) else "FAIL",campaign=pipeline.campaign,components=tuple(items),policy_reference=PR265_POLICY,production_authorized=False)
    return RuntimeCertification(**values,replay_identity=certification_identity("V28_RUNTIME_CERTIFICATION",values))
