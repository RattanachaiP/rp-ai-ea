import json
import os
import pytest
from bridge.v28.publisher import AtomicDecisionPublisher, DecisionPathOwnership, OwnershipError, PublicationError
from tests.test_schema import decision


def test_atomic_publish_cleans_stale_temporary(tmp_path):
    path = tmp_path / "decision.json"; temporary = tmp_path / "decision.json.tmp"; temporary.write_text("stale")
    AtomicDecisionPublisher(path).publish(decision())
    assert json.loads(path.read_text())["decision"] == "HOLD" and not temporary.exists()


def test_publisher_failure_preserves_previous_decision(tmp_path, monkeypatch):
    path = tmp_path / "decision.json"; publisher = AtomicDecisionPublisher(path); publisher.publish(decision())
    previous = path.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(PublicationError): publisher.publish(decision())
    assert path.read_bytes() == previous and not publisher.temporary.exists()


def test_single_writer_conflict(tmp_path):
    first = DecisionPathOwnership(tmp_path / "decision.json"); second = DecisionPathOwnership(tmp_path / "decision.json")
    first.acquire()
    try:
        with pytest.raises(OwnershipError): second.acquire()
    finally: first.release()
