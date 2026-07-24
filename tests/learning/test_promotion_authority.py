"""PR156 promotion authority execution and failure-closure regressions."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import pytest
from learning.promotion_authority import PromotionAuthority, PromotionAuthorityConfig

def report_at(timestamp):
    # The authority consumes the report only; build a complete signed report contract.
    from learning.promotion_decision.models import PromotionDecisionReport
    from hashlib import sha256
    import json
    decision, knowledge = str(uuid4()), str(uuid4())
    unsigned={"decision_uuid":decision,"knowledge_uuid":knowledge,"decision":"PROMOTE","decision_status":"APPROVED","reason":[],"blocking_conditions":[],"snapshot_digest":"a"*64,"qualification_digest":"b"*64,"policy_version":"1.0","created_at":timestamp,"schema_version":"1.0","configuration_digest":"c"*64}
    signature=sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return PromotionDecisionReport(**unsigned, signature=signature)

def authority(tmp_path, lifecycle=None, now=None):
    now=now or datetime.now(timezone.utc)
    return PromotionAuthority(root=tmp_path, lifecycle_service=lifecycle or (lambda **v:v), clock=lambda:now)

def test_valid_promotion_is_idempotent_and_append_only(tmp_path):
    report=report_at(datetime.now(timezone.utc).isoformat())
    service=lambda **value:value
    result=authority(tmp_path,service).execute(report)
    repeated=authority(tmp_path,service).execute(report)
    assert result.to_dict()==repeated.to_dict()
    assert len(authority(tmp_path).history())==1
    with pytest.raises(FileExistsError): authority(tmp_path).storage.write(replace(result, operator="other"))

def test_expired_bad_signature_and_non_promote_fail_closed(tmp_path):
    past=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    with pytest.raises(ValueError,match="EXPIRED"): authority(tmp_path).execute(report_at(past))
    current=report_at(datetime.now(timezone.utc).isoformat())
    with pytest.raises(ValueError,match="SIGNATURE"): authority(tmp_path).execute(replace(current,signature="0"*64))
    with pytest.raises(ValueError,match="NOT_EXECUTABLE"): authority(tmp_path).execute(replace(current,decision="REJECT",decision_status="DENIED"))

def test_lifecycle_failure_rolls_back_staged_record(tmp_path):
    def fail(**kwargs): raise RuntimeError("lifecycle unavailable")
    now=datetime.now(timezone.utc)
    with pytest.raises(RuntimeError,match="lifecycle unavailable"): authority(tmp_path,fail,now).execute(report_at(now.isoformat()))
    assert authority(tmp_path).history()==()

def test_candidate_lock_contention_fails_closed(tmp_path):
    instance=authority(tmp_path); semantic="candidate"
    with instance._lock(semantic):
        with pytest.raises(RuntimeError,match="LOCK_CONTENDED"):
            with instance._lock(semantic): pass
