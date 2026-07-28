"""Component-level PASS/WARNING/FAIL certification evidence."""
from dataclasses import dataclass
from .pipeline_validator import PR265_POLICY, PipelineValidationReport, certification_identity

COMPONENTS = ("Runtime Foundation", "Market Intelligence", "Decision Intelligence", "Risk Construction", "Execution Integration")

@dataclass(frozen=True)
class ComponentCertification:
    component: str; status: str; evidence: tuple[str, ...]
    def __post_init__(self):
        if self.component not in COMPONENTS or self.status not in {"PASS", "WARNING", "FAIL"} or not self.evidence: raise ValueError("COMPONENT_CERTIFICATION_INVALID")

@dataclass(frozen=True)
class RuntimeCertification:
    status: str; components: tuple[ComponentCertification, ...]; policy_reference: str
    production_authorized: bool; replay_identity: str
    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.status not in {"PASS", "FAIL"} or self.production_authorized is not False: raise ValueError("RUNTIME_CERTIFICATION_INVALID")
        if tuple(x.component for x in self.components) != COMPONENTS: raise ValueError("CERTIFICATION_COMPONENTS_INCOMPLETE")
        if self.replay_identity != certification_identity("V28_RUNTIME_CERTIFICATION", self.canonical_payload()): raise ValueError("RUNTIME_CERTIFICATION_REPLAY_INVALID")

def certify_runtime(report: PipelineValidationReport) -> RuntimeCertification:
    boundary = {item.boundary: item for item in report.boundaries}
    sources = (("Runtime Foundation", ("RISK_TO_EXECUTION",)), ("Market Intelligence", ("MARKET_TO_DECISION",)),
               ("Decision Intelligence", ("MARKET_TO_DECISION", "DECISION_TO_RISK")),
               ("Risk Construction", ("DECISION_TO_RISK", "RISK_TO_EXECUTION")),
               ("Execution Integration", ("RISK_TO_EXECUTION", "EXECUTION_TO_PUBLICATION")))
    components = []
    for name, names in sources:
        missing = [key for key in names if key not in boundary]
        failed = [key for key in names if key in boundary and boundary[key].status == "FAIL"]
        status = "FAIL" if failed else "WARNING" if missing else "PASS"
        evidence = tuple(failed or missing or names)
        components.append(ComponentCertification(name, status, evidence))
    status = "PASS" if all(item.status == "PASS" for item in components) else "FAIL"
    values = dict(status=status, components=tuple(components), policy_reference=PR265_POLICY, production_authorized=False)
    return RuntimeCertification(**values, replay_identity=certification_identity("V28_RUNTIME_CERTIFICATION", values))
