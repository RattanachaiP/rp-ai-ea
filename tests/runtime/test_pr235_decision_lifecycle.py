import json

import pytest

from runtime.decision_publication import (
    DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS,
    DECISION_PRODUCER,
    PUBLISHED_SCHEMA_VERSION,
    RUNTIME_VERSION,
)
from runtime.market_state_reader import PRODUCER as MARKET_PRODUCER
from runtime.market_state_reader import PRODUCER_VERSION as MARKET_PRODUCER_VERSION
from runtime.runtime_observability import (
    DecisionBlockReason,
    FAILURE_OWNERS,
    LEGACY_FAILURE_REASONS,
    PublicationOutcome,
    PublicationVerificationFailure,
    RuntimeObservability,
)


NOW = 1_785_230_400
MARKET_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"
DECISION_UUID = "00000000-0000-4000-8000-000000000235"
REQUIRED_NORMAL_FIELDS = (
    "decision_uuid", "sequence_id", "heartbeat_unix", "producer",
    "producer_version", "schema_version", "decision_lifecycle", "confidence",
    "market_state_sequence_id", "market_state_source_uuid", "decision",
    "decision_timestamp", "timestamp",
)


def market(sequence=41):
    return {"sequence_id": sequence, "heartbeat_unix": NOW,
            "producer": MARKET_PRODUCER, "producer_version": MARKET_PRODUCER_VERSION,
            "source_uuid": MARKET_UUID}


def decision(sequence=1):
    return {"decision_uuid": DECISION_UUID, "sequence_id": sequence,
            "market_state_sequence_id": 41, "market_state_source_uuid": MARKET_UUID,
            "heartbeat_unix": NOW, "producer": DECISION_PRODUCER,
            "producer_version": RUNTIME_VERSION, "schema_version": PUBLISHED_SCHEMA_VERSION,
            "decision_lifecycle": "GOVERNED_NO_TRADE", "decision": "NO_TRADE",
            "confidence": 64.0, "active_profile": "DEFAULT",
            "decision_timestamp": "2026-07-28T00:00:00Z",
            "timestamp": "2026-07-28T00:00:00Z"}


def observer(tmp_path, *, accept_market=True):
    value = RuntimeObservability(tmp_path, clock=lambda: NOW)
    if accept_market:
        value.market_state(market())
    return value


def assert_rejected(value, tmp_path, owner, reason):
    health = value.snapshot()
    assert health["runtime_started"] is False
    assert health["status"] == "STARTING"
    assert health["health_state"] == "DEGRADED"
    assert health["failure_owner"] == owner
    assert health["failure_reason"] == reason.value
    assert health["failure_detail"]
    assert health["promotion_invariant"] == reason.value
    assert health["publication_count"] == health["successful_loop_count"] == 0
    assert health["first_normal_decision_at"] is None
    assert not (tmp_path / "first_normal_decision.json").exists()
    assert not (tmp_path / "first_decision.json").exists()
    assert "REJECTED" in (tmp_path / "decision_pipeline_trace.log").read_text()
    assert not tuple(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("field", REQUIRED_NORMAL_FIELDS)
def test_every_missing_required_field_fails_closed(tmp_path, field):
    value = observer(tmp_path)
    document = decision()
    document.pop(field)
    with pytest.raises(PublicationVerificationFailure) as raised:
        value.publication(document, 1, PublicationOutcome.NORMAL)
    assert raised.value.owner == "PUBLISHER"
    assert raised.value.reason is DecisionBlockReason.INVALID_SCHEMA
    assert_rejected(value, tmp_path, "PUBLISHER", DecisionBlockReason.INVALID_SCHEMA)


@pytest.mark.parametrize(("change", "reason"), [
    ({"decision_uuid": "invalid"}, DecisionBlockReason.INVALID_SCHEMA),
    ({"producer": "WRONG"}, DecisionBlockReason.INVALID_SCHEMA),
    ({"producer_version": "WRONG"}, DecisionBlockReason.INVALID_SCHEMA),
    ({"schema_version": "WRONG"}, DecisionBlockReason.INVALID_SCHEMA),
    ({"market_state_sequence_id": 42}, DecisionBlockReason.DECISION_REJECTED),
    ({"market_state_source_uuid": "00000000-0000-4000-8000-000000000000"},
     DecisionBlockReason.DECISION_REJECTED),
])
def test_invalid_identity_contract_or_market_lineage_fails_closed(tmp_path, change, reason):
    value = observer(tmp_path)
    with pytest.raises(PublicationVerificationFailure):
        value.publication(decision() | change, 1, PublicationOutcome.NORMAL)
    assert_rejected(value, tmp_path, "PUBLISHER", reason)


def test_no_accepted_market_state_fails_closed(tmp_path):
    value = observer(tmp_path, accept_market=False)
    with pytest.raises(PublicationVerificationFailure):
        value.publication(decision(), 1, PublicationOutcome.NORMAL)
    assert_rejected(value, tmp_path, "READER", DecisionBlockReason.NO_MARKET_STATE)


def test_stale_heartbeat_uses_injected_clock(tmp_path):
    value = observer(tmp_path)
    stale = decision() | {
        "heartbeat_unix": NOW - DECISION_HEARTBEAT_MAXIMUM_AGE_SECONDS - 1,
    }
    with pytest.raises(PublicationVerificationFailure):
        value.publication(stale, 1, PublicationOutcome.NORMAL)
    assert_rejected(value, tmp_path, "PUBLISHER", DecisionBlockReason.STALE_MARKET_STATE)


def test_first_normal_decision_and_runtime_promotion(tmp_path):
    value = observer(tmp_path)
    for stage in ("DECISION CONTEXT", "ANALYSIS", "RISK CONSTRUCTION", "DECISION CLASSIFICATION"):
        value.stage(stage)
    value.publication(decision(), 2.5, PublicationOutcome.NORMAL)
    health = value.snapshot()
    assert health["status"] == "RUNNING" and health["health_state"] == "HEALTHY"
    assert health["runtime_started"] is True
    assert health["publication_count"] == health["successful_loop_count"] == 1
    assert health["first_normal_decision_at"] and health["promotion_invariant"] is None
    assert health["failure_owner"] is health["failure_reason"] is health["failure_detail"] is None
    evidence = json.loads((tmp_path / "first_normal_decision.json").read_text())
    assert set(evidence) == {"decision_uuid", "market_sequence", "heartbeat_unix", "producer",
                             "producer_version", "decision_type", "confidence", "risk_profile",
                             "publication_timestamp"}
    assert json.loads((tmp_path / "first_decision.json").read_text()) == decision()
    transitions = (tmp_path / "runtime_transition.log").read_text()
    assert "STARTING -> RUNNING" in transitions and "RUNNING -> HEALTHY" in transitions
    assert not tuple(tmp_path.glob("*.tmp"))


def test_non_monotonic_failure_after_running_and_recovery(tmp_path):
    value = observer(tmp_path)
    value.publication(decision(5), 1, PublicationOutcome.NORMAL)
    immutable = (tmp_path / "first_normal_decision.json").read_bytes()
    with pytest.raises(PublicationVerificationFailure):
        value.publication(decision(5), 1, PublicationOutcome.NORMAL)
    degraded = value.snapshot()
    assert degraded["status"] == "RUNNING" and degraded["health_state"] == "DEGRADED"
    assert degraded["runtime_started"] is True
    assert degraded["failure_owner"] == "PUBLISHER"
    assert degraded["failure_reason"] == DecisionBlockReason.DECISION_REJECTED.value
    assert degraded["publication_count"] == degraded["successful_loop_count"] == 1
    assert degraded["exception_count"] == 1
    assert (tmp_path / "first_normal_decision.json").read_bytes() == immutable

    value.publication(decision(6), 1, PublicationOutcome.NORMAL)
    recovered = value.snapshot()
    assert recovered["status"] == "RUNNING" and recovered["health_state"] == "HEALTHY"
    assert recovered["failure_owner"] is recovered["failure_reason"] is None
    assert recovered["failure_detail"] is None and recovered["exception_count"] == 1
    assert recovered["publication_count"] == recovered["successful_loop_count"] == 2
    assert (tmp_path / "first_normal_decision.json").read_bytes() == immutable
    assert not tuple(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("owner", sorted(FAILURE_OWNERS))
def test_owner_and_reason_are_separate(tmp_path, owner):
    value = observer(tmp_path, accept_market=False)
    value.failure(owner, RuntimeError("controlled diagnostic"))
    health = value.snapshot()
    assert health["failure_owner"] == owner
    assert health["failure_reason"] == LEGACY_FAILURE_REASONS[owner].value
    assert health["failure_owner"] != health["failure_reason"]
