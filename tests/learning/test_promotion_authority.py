"""PR156 promotion authority execution and failure-closure regressions."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

from learning.promotion_authority import PromotionAuthority, PromotionAuthorityConfig
from learning.promotion_decision.models import PromotionDecisionReport


def report_at(timestamp: str, *, semantic_identity: str = "family/xauusd/pattern-1") -> PromotionDecisionReport:
    decision, knowledge = str(uuid4()), str(uuid4())
    unsigned = {
        "decision_uuid": decision,
        "knowledge_uuid": knowledge,
        "decision": "PROMOTE",
        "decision_status": "APPROVED",
        "reason": [],
        "blocking_conditions": [],
        "snapshot_digest": "a" * 64,
        "qualification_digest": "b" * 64,
        "policy_version": "1.0",
        "created_at": timestamp,
        "schema_version": "1.0",
        "configuration_digest": "c" * 64,
        "semantic_identity": semantic_identity,
    }
    signature = sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PromotionDecisionReport(**unsigned, signature=signature)


def authority(tmp_path: Path, report: PromotionDecisionReport, lifecycle=None, now=None, **changes) -> PromotionAuthority:
    now = now or datetime.now(timezone.utc)
    config = PromotionAuthorityConfig(
        trusted_decision_signatures={report.decision_uuid: report.signature},
        approved_configuration_digests=(report.configuration_digest,),
        **changes,
    )
    return PromotionAuthority(config=config, root=tmp_path, lifecycle_service=lifecycle or (lambda **value: value), clock=lambda: now)


def test_valid_promotion_is_idempotent_and_append_only(tmp_path):
    now = datetime.now(timezone.utc)
    report = report_at(now.isoformat())
    service = lambda **value: value
    result = authority(tmp_path, report, service, now).execute(report)
    repeated = authority(tmp_path, report, service, now).execute(report)
    assert result.to_dict() == repeated.to_dict()
    history = authority(tmp_path, report, service, now).history()
    assert [record.status for record in history] == ["PREPARED", "COMMITTED"]
    with pytest.raises(FileExistsError):
        authority(tmp_path, report, service, now).storage.write(replace(result, operator="other"))


def test_untrusted_expired_tampered_and_non_promote_fail_closed(tmp_path):
    now = datetime.now(timezone.utc)
    current = report_at(now.isoformat())
    untrusted = PromotionAuthorityConfig(approved_configuration_digests=(current.configuration_digest,))
    with pytest.raises(ValueError, match="UNTRUSTED"):
        PromotionAuthority(config=untrusted, root=tmp_path, lifecycle_service=lambda **value: value, clock=lambda: now).execute(current)
    past = report_at((now - timedelta(hours=2)).isoformat())
    with pytest.raises(ValueError, match="EXPIRED"):
        authority(tmp_path, past, now=now).execute(past)
    with pytest.raises(ValueError, match="UNTRUSTED|SIGNATURE"):
        authority(tmp_path, current, now=now).execute(replace(current, signature="0" * 64))
    forged = replace(current, decision="REJECT", decision_status="DENIED")
    with pytest.raises(ValueError, match="NOT_EXECUTABLE"):
        authority(tmp_path, current, now=now).execute(forged)


def test_lifecycle_failure_preserves_in_doubt_audit_evidence(tmp_path):
    def fail(**kwargs):
        raise RuntimeError("lifecycle unavailable")
    now = datetime.now(timezone.utc)
    report = report_at(now.isoformat())
    with pytest.raises(RuntimeError, match="lifecycle unavailable"):
        authority(tmp_path, report, fail, now).execute(report)
    history = authority(tmp_path, report, lambda **value: value, now).history()
    assert [record.status for record in history] == ["PREPARED", "IN_DOUBT"]
    assert history[-1].previous_record_uuid == history[0].record_uuid


def test_lifecycle_contract_requires_cas_and_idempotency(tmp_path):
    now = datetime.now(timezone.utc)
    report = report_at(now.isoformat())
    captured = {}
    def service(**kwargs):
        captured.update(kwargs)
        return kwargs
    authority(tmp_path, report, service, now).execute(report)
    assert captured["expected_current_state"] == "VERIFIED"
    assert captured["new_state"] == "ACTIVE"
    assert captured["idempotency_key"] == report.decision_uuid


def test_candidate_lock_contention_and_stale_recovery(tmp_path):
    now = datetime.now(timezone.utc)
    report = report_at(now.isoformat())
    instance = authority(tmp_path, report, now=now, lock_lease_seconds=10)
    with instance._lock("candidate"):
        with pytest.raises(RuntimeError, match="LOCK_CONTENDED"):
            with instance._lock("candidate"):
                pass
    lock_dir = tmp_path / "promotion_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / (sha256(b"stale").hexdigest() + ".lock")
    lock_path.write_text(json.dumps({"owner": "dead", "pid": 1, "host": "old", "acquired_at": (now - timedelta(minutes=1)).isoformat()}))
    with instance._lock("stale"):
        assert True


def test_same_semantic_identity_serializes_different_knowledge(tmp_path):
    now = datetime.now(timezone.utc)
    first = report_at(now.isoformat(), semantic_identity="shared-slot")
    second = report_at(now.isoformat(), semantic_identity="shared-slot")
    first_authority = authority(tmp_path, first, now=now)
    with first_authority._lock("shared-slot"):
        with pytest.raises(RuntimeError, match="LOCK_CONTENDED"):
            with authority(tmp_path, second, now=now)._lock("shared-slot"):
                pass
