import json
import time
from datetime import datetime, timezone

import pytest

from runtime.runtime_observability import DecisionBlockReason, PublicationOutcome, RuntimeObservability


MARKET_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"
DECISION_UUID = "00000000-0000-4000-8000-000000000235"


def market(sequence=41):
    return {"sequence_id": sequence, "heartbeat_unix": 1_900_000_000,
            "producer": "RP_AI_MT5_MARKET_STATE", "producer_version": "V1",
            "source_uuid": MARKET_UUID}


def decision(sequence=1):
    now = int(time.time())
    return {"decision_uuid": DECISION_UUID, "sequence_id": sequence,
            "market_state_sequence_id": 41, "market_state_source_uuid": MARKET_UUID,
            "heartbeat_unix": now, "producer": "RP_AI_DECISION_ENGINE",
            "producer_version": "V27", "decision_lifecycle": "GOVERNED_NO_TRADE",
            "decision": "NO_TRADE", "confidence": 64.0, "active_profile": "DEFAULT",
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")}


def test_first_normal_decision_and_runtime_promotion(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.market_state(market())
    for stage in ("DECISION CONTEXT", "ANALYSIS", "RISK CONSTRUCTION", "DECISION CLASSIFICATION"):
        observer.stage(stage)
    observer.publication(decision(), 2.5, PublicationOutcome.NORMAL)

    health = json.loads((tmp_path / "runtime_health.json").read_text())
    assert health["status"] == "RUNNING"
    assert health["health_state"] == "HEALTHY"
    assert health["promotion_invariant"] is None
    evidence = json.loads((tmp_path / "first_normal_decision.json").read_text())
    assert set(evidence) == {"decision_uuid", "market_sequence", "heartbeat_unix", "producer",
                             "producer_version", "decision_type", "confidence", "risk_profile",
                             "publication_timestamp"}
    assert evidence["market_sequence"] == 41
    assert "STARTING -> RUNNING" in (tmp_path / "runtime_transition.log").read_text()
    assert "RUNNING -> HEALTHY" in (tmp_path / "runtime_transition.log").read_text()


@pytest.mark.parametrize("reason", tuple(DecisionBlockReason))
def test_rejection_has_exactly_one_canonical_owner(tmp_path, reason):
    observer = RuntimeObservability(tmp_path)
    observer.failure(reason.value, RuntimeError("irrelevant internal detail"))
    health = observer.snapshot()
    assert health["failure_owner"] == health["failure_reason"] == reason.value
    assert "decision failed" not in (tmp_path / "decision_pipeline_trace.log").read_text().lower()


def test_publication_integrity_is_fail_closed(tmp_path):
    observer = RuntimeObservability(tmp_path)
    observer.market_state(market())
    observer.publication(decision(), 1, PublicationOutcome.NORMAL)
    with pytest.raises(ValueError, match="PUBLICATION_FAILED"):
        observer.publication(decision(), 1, PublicationOutcome.NORMAL)
    broken = decision(2) | {"market_state_source_uuid": "00000000-0000-4000-8000-000000000000"}
    with pytest.raises(ValueError, match="INVALID_SCHEMA"):
        observer.publication(broken, 1, PublicationOutcome.NORMAL)
    assert not tuple(tmp_path.glob("*.tmp"))
