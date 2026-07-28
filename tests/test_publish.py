import json
from bridge.v28.publisher import AtomicDecisionPublisher


def test_atomic_publish_replaces_complete_document(tmp_path):
    path = tmp_path / "decision.json"; path.write_text('{"old":true}')
    AtomicDecisionPublisher(path).publish({"decision": "HOLD", "sequence_id": 3})
    assert json.loads(path.read_text()) == {"decision": "HOLD", "sequence_id": 3}
    assert not (tmp_path / "decision.json.tmp").exists()
