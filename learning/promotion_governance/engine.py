"""Deterministic, fail-closed governance for qualified promotion candidates."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5
from .models import PromotionAudit, PromotionDecision, PromotionPackage, PromotionPolicy
from .storage import PromotionHistoryStorage

def _canonical(v: Any) -> str: return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
def _digest(v: Any) -> str: return sha256(_canonical(v).encode()).hexdigest()
def _data(v: Any) -> dict[str, Any] | None:
    if hasattr(v, "to_dict"): v=v.to_dict()
    return dict(v) if isinstance(v, Mapping) else None
def _uuid(v: Any) -> str | None:
    try: return str(UUID(v)) if isinstance(v,str) and str(UUID(v)) == v.lower() else None
    except (ValueError, TypeError, AttributeError): return None
def _time(v: Any) -> datetime | None:
    try:
        x=datetime.fromisoformat(v.replace("Z","+00:00")); return x if x.tzinfo else None
    except (ValueError, AttributeError): return None

def _score(data: Mapping[str, Any], name: str) -> int | None:
    value=data.get(name)
    return value if isinstance(value,int) and not isinstance(value,bool) and 0 <= value <= 100 else None

class PromotionGovernance:
    """PR165's sole authorization boundary; it has no activation side effects."""
    def __init__(self, policy: PromotionPolicy | None=None, *, root="learning_data"):
        self.policy=policy or PromotionPolicy(); self.storage=PromotionHistoryStorage(root)
    def evaluate(self, qualification_decision: Any, qualification_evidence: Any,
                 qualification_summary: Any, *, approver: str = "", approval_timestamp: str = "") -> PromotionPackage:
        decision,evidence,summary=(_data(x) for x in (qualification_decision,qualification_evidence,qualification_summary))
        # No wall clock is read: repeated evaluation of identical artifacts is identical.
        now = (_time(self.policy.evaluation_timestamp) or _time((decision or {}).get("created_at", ""))
               or datetime(1970, 1, 1, tzinfo=timezone.utc))
        # All decision identity derives only from supplied qualification artifacts and policy.
        source={"decision":decision,"evidence":evidence,"summary":summary,"policy":self.policy.canonical_dict()}
        replay=_digest(source)
        candidate = (decision or {}).get("candidate_uuid") or (summary or {}).get("candidate_uuid") or (evidence or {}).get("candidate_uuid")
        knowledge = (decision or {}).get("knowledge_uuid") or (summary or {}).get("knowledge_uuid") or (evidence or {}).get("knowledge_uuid")
        candidate_id, knowledge_id = _uuid(candidate), _uuid(knowledge)
        identity=str(uuid5(NAMESPACE_URL,replay))
        def result(state: str, reason: str, digest: str="0"*64) -> PromotionPackage:
            # UUID model validation needs IDs; unknown input cannot produce a valid authorization.
            cid=candidate_id or str(uuid5(NAMESPACE_URL,"invalid-candidate:"+replay)); kid=knowledge_id or str(uuid5(NAMESPACE_URL,"invalid-knowledge:"+replay))
            return PromotionPackage(PromotionDecision(identity,cid,kid,state,reason,self.policy.version,self.policy.architecture_version,digest,replay,now.isoformat().replace("+00:00","Z"),state == "APPROVED"))
        if not all((decision,evidence,summary)) or not candidate_id or not knowledge_id: return result("REJECTED","MISSING_OR_INVALID_UUID")
        qdigest=_digest({"decision":decision,"evidence":evidence,"summary":summary})
        if decision.get("status") not in {"QUALIFIED", "APPROVED"} or decision.get("qualified") is not True: return result("REJECTED","INVALID_QUALIFICATION",qdigest)
        if evidence.get("integrity_digest") not in {_digest(evidence.get("payload")), _digest({k:v for k,v in evidence.items() if k != "integrity_digest"})}: return result("REJECTED","CORRUPTED_EVIDENCE",qdigest)
        if evidence.get("replay_digest") and evidence["replay_digest"] != _digest(summary): return result("REJECTED","REPLAY_MISMATCH",qdigest)
        if summary.get("policy_version") != self.policy.version or summary.get("architecture_version") != self.policy.architecture_version: return result("REJECTED","INVALID_POLICY",qdigest)
        scores=(("scientific_score",self.policy.minimum_scientific_score),("statistical_score",self.policy.minimum_statistical_score),("governance_score",self.policy.minimum_governance_score))
        if any((s:=_score(summary,n)) is None or s < minimum for n,minimum in scores): return result("REJECTED","INSUFFICIENT_QUALIFICATION_SCORES",qdigest)
        created=_time(decision.get("created_at", ""))
        if created and (now-created).total_seconds() > self.policy.decision_ttl_seconds: return result("EXPIRED","QUALIFICATION_EXPIRED",qdigest)
        if any(a.knowledge_uuid == knowledge_id for a in self.storage.all()): return result("REJECTED","DUPLICATE_PROMOTION",qdigest)
        if not approver or not approval_timestamp or not _time(approval_timestamp): return result("DEFERRED","HUMAN_APPROVAL_REQUIRED",qdigest)
        audit=PromotionAudit(identity,candidate_id,knowledge_id,approval_timestamp,approver,self.policy.version,self.policy.architecture_version,"MANUAL_APPROVAL")
        return PromotionPackage(PromotionDecision(identity,candidate_id,knowledge_id,"APPROVED","MANUAL_APPROVAL",self.policy.version,self.policy.architecture_version,qdigest,replay,now.isoformat().replace("+00:00","Z"),True),audit)
    def authorize(self, *args: Any, **kwargs: Any) -> PromotionPackage:
        package=self.evaluate(*args,**kwargs)
        if package.audit: self.storage.write(package.audit)
        return package
    def history(self): return self.storage.all()
