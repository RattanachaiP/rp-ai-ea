"""Fail-closed planning and authorization; deliberately no activation capability."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
from .models import (HumanApproval, RollbackAssessment, RollbackAudit, RollbackAuthorization, RollbackDecision, RollbackPackage, RollbackPlan, RollbackPolicy, RollbackRequest, valid_digest, valid_time, valid_uuid)
from .storage import RollbackStorage

def _canon(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
def _digest(value): return sha256(_canon(value).encode()).hexdigest()
def _data(value):
    if hasattr(value, "to_dict"): value = value.to_dict()
    if not isinstance(value, Mapping): raise ValueError("INVALID_ROLLBACK_INPUT")
    return json.loads(_canon(dict(value)))
def _dt(value): return datetime.fromisoformat(value.replace("Z", "+00:00")) if valid_time(value) else None
def _iso(value): return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

class RollbackOrchestrator:
    """PR169 sole rollback authority. It emits evidence and never mutates dependencies."""
    def __init__(self, policy: RollbackPolicy | None = None, *, root="learning_data"):
        self.policy = policy or RollbackPolicy(); self.storage = RollbackStorage(root)

    def orchestrate(self, request: RollbackRequest | Mapping[str, Any], current_version: Any, target_version: Any,
                    descriptor: Any, current_manifest: Any, target_manifest: Any, current_registry_snapshot: Any,
                    target_registry_snapshot: Any, *, approval: HumanApproval | Mapping[str, Any] | None = None) -> RollbackPackage:
        req = request if isinstance(request, RollbackRequest) else RollbackRequest(**_data(request))
        current, target, desc, cm, tm, cs, ts = (_data(x) for x in (current_version, target_version, descriptor, current_manifest, target_manifest, current_registry_snapshot, target_registry_snapshot))
        source = {"request": req.to_dict(), "current": current, "target": target, "descriptor": desc, "current_manifest": cm, "target_manifest": tm, "current_registry_snapshot": cs, "target_registry_snapshot": ts, "policy": self.policy.to_dict()}
        replay = _digest(source); now = _dt(self.policy.evaluation_timestamp) or _dt(req.requested_at) or datetime(1970, 1, 1, tzinfo=timezone.utc)
        rollback_id = str(uuid5(NAMESPACE_URL, "rollback:" + replay)); created = _iso(now)
        def package(state, reason, auth=None, plan=None):
            decision = RollbackDecision(rollback_id, req.request_uuid, req.knowledge_uuid, req.current_version_uuid, req.target_version_uuid, state, reason, self.policy.version, self.policy.architecture_version, replay, created)
            audit = RollbackAudit(rollback_id, req.request_uuid, state, created, reason)
            return RollbackPackage(decision, auth, plan, audit, cm, tm, cs, ts)
        # Identity, immutability, source manifests, and all contracts are independently checked.
        if any(not valid_uuid(x) for x in (current.get("version_uuid"), target.get("version_uuid"))) or current.get("version_uuid") != req.current_version_uuid or target.get("version_uuid") != req.target_version_uuid: return package("REJECTED", "INVALID_VERSION_UUID")
        if current.get("knowledge_uuid") != req.knowledge_uuid or target.get("knowledge_uuid") != req.knowledge_uuid: return package("REJECTED", "CROSS_KNOWLEDGE")
        if not all(valid_digest(x.get("version_digest")) for x in (current, target)): return package("REJECTED", "INVALID_DIGEST")
        if cm.get("version_uuid") != req.current_version_uuid or tm.get("version_uuid") != req.target_version_uuid or not all(valid_digest(x.get("manifest_digest")) for x in (cm, tm)): return package("REJECTED", "MISSING_OR_INVALID_MANIFEST")
        if not isinstance(cs, Mapping) or not isinstance(ts, Mapping) or not cs or not ts: return package("REJECTED", "MISSING_REGISTRY_SNAPSHOT")
        required = {"architecture_version", "policy_version", "registry_version", "runtime_contract", "knowledge_contract", "applicability_contract"}
        cc, tc = cm.get("compatibility", {}), tm.get("compatibility", {})
        if not isinstance(cc, Mapping) or not isinstance(tc, Mapping) or not required.issubset(cc) or not required.issubset(tc) or any(cc[x] != tc[x] for x in required) or cc["architecture_version"] != self.policy.architecture_version or cc["policy_version"] != self.policy.version: return package("REJECTED", "CONTRACT_MISMATCH")
        if desc.get("version_uuid") != req.current_version_uuid or desc.get("rollback_parent_uuid") != req.target_version_uuid or desc.get("eligible") is not True or desc.get("compatible") is not True: return package("REJECTED", "INVALID_LINEAGE")
        if target.get("parent_version_uuid") == req.current_version_uuid or target.get("rollback_parent_uuid") == req.current_version_uuid: return package("REJECTED", "ROLLBACK_LOOP")
        expires = _dt(req.expires_at) if req.expires_at else None
        if expires and now > expires: return package("EXPIRED", "REQUEST_EXPIRED")
        # Duplicate identity is rejected except an exact replay, which is returned deterministically.
        package_path = self.storage.root / "packages" / f"{rollback_id}.json"
        if package_path.exists():
            prior = json.loads(package_path.read_text(encoding="utf-8"))
            if prior.get("decision", {}).get("replay_digest") == replay: return self._load_package(prior)
            return package("REJECTED", "REPLAY_MISMATCH")
        if approval is None: return package("AWAITING_APPROVAL", "HUMAN_APPROVAL_REQUIRED")
        approval = approval if isinstance(approval, HumanApproval) else HumanApproval(**_data(approval))
        expiry = now + timedelta(seconds=self.policy.authorization_ttl_seconds)
        if _dt(approval.approved_at) > expiry: return package("EXPIRED", "AUTHORIZATION_EXPIRED")
        authorization = RollbackAuthorization(rollback_id, approval.approver, approval.approved_at, approval.reason, _iso(expiry))
        plan = RollbackPlan(rollback_id, req.current_version_uuid, req.target_version_uuid, _digest(cs), _digest(ts), created, _iso(expiry))
        return package("AUTHORIZED", "MANUAL_APPROVAL", authorization, plan)

    def authorize(self, *args, **kwargs):
        result = self.orchestrate(*args, **kwargs)
        # Only authorized requests are persisted as executable packages; rejected assessments stay pure.
        if result.decision.state == "AUTHORIZED":
            rid = result.decision.rollback_uuid
            self.storage.write("requests", f"request_{rid}", {"request": result.decision.request_uuid, "replay_digest": result.decision.replay_digest})
            self.storage.write("plans", f"plan_{rid}", result.plan)
            self.storage.write("audits", f"audit_{rid}", result.audit)
            self.storage.write("history", f"history_{rid}", result.audit)
            self.storage.write("packages", rid, result)
        return result
    evaluate = orchestrate
    def _load_package(self, data):
        return RollbackPackage(RollbackDecision(**data["decision"]), RollbackAuthorization(**data["authorization"]) if data.get("authorization") else None, RollbackPlan(**data["plan"]) if data.get("plan") else None, RollbackAudit(**data["audit"]), data.get("current_manifest", {}), data.get("target_manifest", {}), data.get("current_registry_snapshot", {}), data.get("target_registry_snapshot", {}))
