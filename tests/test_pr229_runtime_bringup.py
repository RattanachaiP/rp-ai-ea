"""PR229 live runtime identity and configuration checks."""

import importlib
from datetime import datetime
from pathlib import Path
from uuid import UUID


def test_every_published_decision_gets_complete_unique_identity():
    engine = importlib.import_module(
        "bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine"
    )
    first = engine.attach_decision_identity({"bias": "BUY", "confidence": 72})
    second = engine.attach_decision_identity({"action": "SELL", "execution_confidence_score": 65})

    UUID(first["decision_uuid"])
    UUID(second["decision_uuid"])
    assert first["decision_uuid"] != second["decision_uuid"]
    assert datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00")).tzinfo
    assert first["decision_timestamp"] == first["timestamp"]
    assert (first["confidence"], first["direction"]) == (72.0, "BUY")
    assert (second["confidence"], second["direction"]) == (65.0, "SELL")


def test_runtime_shared_root_can_be_loaded_from_configuration(monkeypatch, tmp_path):
    module_name = "bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine"
    engine = importlib.import_module(module_name)
    monkeypatch.setenv("RP_AI_SHARED_ROOT", str(tmp_path))
    engine = importlib.reload(engine)

    assert engine.BASE_PATH == Path(tmp_path) / "XAUUSD"
    assert engine.FILE_PATH == Path(tmp_path) / "XAUUSD" / "market_state.json"
    assert engine.OUTPUT_PATH == Path(tmp_path) / "XAUUSD" / "decision.json"
    monkeypatch.delenv("RP_AI_SHARED_ROOT")
    importlib.reload(engine)
