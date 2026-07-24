from uuid import uuid4
from learning.rollback_orchestration import HumanApproval, RollbackOrchestrator, RollbackPolicy, RollbackRequest

def inputs():
    now = "2026-07-24T00:00:00Z"; knowledge, target, current, request = (str(uuid4()) for _ in range(4))
    contracts = {"architecture_version":"PR169","policy_version":"1.0","registry_version":"1","runtime_contract":"r1","knowledge_contract":"k1","applicability_contract":"a1"}
    def version(identity, parent=""): return {"version_uuid":identity,"knowledge_uuid":knowledge,"version_digest":"a"*64,"parent_version_uuid":parent,"rollback_parent_uuid":parent}
    def manifest(identity): return {"version_uuid":identity,"manifest_digest":"b"*64,"compatibility":contracts}
    return (RollbackRequest(request, knowledge, current, target, "health incident", now), version(current, target), version(target), {"version_uuid":current,"rollback_parent_uuid":target,"eligible":True,"compatible":True}, manifest(current), manifest(target), {"registry_version":"1","knowledge_uuid":knowledge}, {"registry_version":"1","knowledge_uuid":knowledge})

def test_valid_rollback_is_deterministic_append_only_and_runtime_isolated(tmp_path):
    values = inputs(); policy = RollbackPolicy(evaluation_timestamp="2026-07-24T00:00:00Z"); approval = HumanApproval("governor", "2026-07-24T00:00:00Z", "approved")
    service = RollbackOrchestrator(policy, root=tmp_path); result = service.authorize(*values, approval=approval); repeat = service.authorize(*values, approval=approval)
    assert result.decision.state == "AUTHORIZED" and result.to_dict() == repeat.to_dict()
    assert not (tmp_path / "runtime").exists() and not (tmp_path / "active_registry").exists()
    assert (tmp_path / "rollback_orchestration" / "packages").exists()

def test_missing_approval_invalid_lineage_and_loop_fail_closed(tmp_path):
    values = inputs(); service = RollbackOrchestrator(RollbackPolicy(evaluation_timestamp="2026-07-24T00:00:00Z"), root=tmp_path)
    assert service.evaluate(*values).decision.state == "AWAITING_APPROVAL"
    broken = list(values); broken[3] = {**broken[3], "eligible":False}; assert service.evaluate(*broken).decision.reason == "INVALID_LINEAGE"
    loop = list(values); loop[2] = {**loop[2], "rollback_parent_uuid":loop[1]["version_uuid"]}; assert service.evaluate(*loop).decision.reason == "ROLLBACK_LOOP"
