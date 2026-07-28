import json
from bridge.v28.decision_contract import build_decision
from bridge.v28.runtime_context import construct_runtime_context
from bridge.decision_writer import DecisionWriter


def test_hold_matches_schema_and_existing_executor_reader(tmp_path):
    schema = json.loads(open("schemas/decision_v28_schema.json", encoding="utf-8").read())
    market = {"symbol": "XAUUSD", "sequence_id": 9, "heartbeat_unix": 100}
    decision = build_decision(construct_runtime_context(market, now=100), now=100)
    assert set(decision) == set(schema["required"])
    assert decision["decision"] == "HOLD" and decision["executable"] is False
    path = tmp_path / "decision.json"; path.write_text(json.dumps(decision))
    result = DecisionWriter(path, clock=lambda: 100).read()
    assert result.accepted and result.payload["decision"] == "HOLD"
