"""Focused PR250 governed acquisition acceptance tests."""
from __future__ import annotations

import json
import math
from pathlib import Path
from uuid import UUID

import pytest

from learning.outcome_evidence import (OutcomeEvidenceError, OutcomeEvidenceManifest,
                                       OutcomeEvidenceRepository, SCHEMA_VERSION,
                                       manifest_digest, row_replay_digest)
from learning.outcome_evidence.operator_acquisition import (construct_pr173, import_evidence,
                                                             inspect, validate)

KNOWLEDGE_UUID = "11111111-1111-5111-8111-111111111111"


def _row(outcome=1.0, timestamp="2026-07-28T10:00:00Z", **changes):
    row = {"knowledge_uuid": KNOWLEDGE_UUID, "knowledge_version": "1.0.0",
           "timestamp": timestamp, "outcome": outcome, "outcome_metric": "REALIZED_PNL",
           "outcome_unit": "USD", "features": {"trend": "up"},
           "indicators": {"rsi": 40}, "risk_factors": {"spread": "normal"},
           "context": {"regime": "TREND"}, "metadata": {"external_event_identity": "deal-verified-1"}}
    row.update(changes)
    if isinstance(row["outcome"], (int, float)) and not isinstance(row["outcome"], bool):
        row["outcome"] = float(row["outcome"])
    payload = {key: value for key, value in row.items() if key != "replay_digest"}
    row["replay_digest"] = row_replay_digest(payload)
    return row


def _manifest(rows=None, **changes):
    payload = {"schema_version": SCHEMA_VERSION, "source_system_identity": "governed-history-export/v1",
               "acquisition_timestamp": "2026-07-28T11:00:00Z",
               "operator_metadata": {"operator_id": "reviewed-operator", "import_ticket": "governed-ticket"},
               "declared_knowledge_identity": {"knowledge_uuid": KNOWLEDGE_UUID, "knowledge_version": "1.0.0"},
               "declared_outcome_contract": {"outcome_metric": "REALIZED_PNL", "outcome_unit": "USD"},
               "evidence_rows": rows or [_row()]}
    payload.update(changes)
    payload["manifest_digest"] = manifest_digest(payload)
    return payload


def _write(path: Path, value) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_file_named_immutable_model_and_deterministic_order_identity(tmp_path):
    rows = [_row(2, "2026-07-28T10:01:00Z"), _row(1)]
    a = OutcomeEvidenceManifest.from_dict(_manifest(rows))
    b = OutcomeEvidenceManifest.from_dict(_manifest(list(reversed(rows))))
    assert a.manifest_digest == b.manifest_digest
    # Canonical admitted evidence and PR173 semantics sort rows independently.
    file_a = _write(tmp_path / "a.json", _manifest(rows))
    file_b = _write(tmp_path / "b.json", _manifest(list(reversed(rows))))
    assert validate(file_a)["source_digest"] == validate(file_b)["source_digest"]
    assert validate(file_a)["replay_digest"] == validate(file_b)["replay_digest"]
    assert isinstance(a.evidence_rows, tuple)


@pytest.mark.parametrize("change,code", [
    ({"evidence_rows": []}, "OUTCOME_EVIDENCE_EMPTY"),
    ({"declared_knowledge_identity": {"knowledge_uuid": "bad", "knowledge_version": "1.0.0"}}, "OUTCOME_EVIDENCE_SCHEMA_INVALID"),
])
def test_empty_and_invalid_declared_uuid(change, code):
    with pytest.raises(OutcomeEvidenceError, match=code):
        OutcomeEvidenceManifest.from_dict(_manifest(**change))


def test_missing_required_field_invalid_timestamp_and_replay_provenance():
    missing = _row(); del missing["outcome"]
    naive = _row(timestamp="2026-07-28T10:00:00")
    replay = _row(); replay["replay_digest"] = "a" * 64
    for row, code in ((missing, "OUTCOME_EVIDENCE_SCHEMA_INVALID"),
                      (naive, "TIMESTAMP_INVALID"), (replay, "REPLAY_PROVENANCE_INVALID")):
        with pytest.raises(OutcomeEvidenceError, match=code):
            OutcomeEvidenceManifest.from_dict(_manifest([row]))


def test_mixed_identity_and_outcome_contract_fail_closed():
    other = _row(knowledge_uuid="22222222-2222-5222-8222-222222222222")
    other["replay_digest"] = row_replay_digest({k: v for k, v in other.items() if k != "replay_digest"})
    with pytest.raises(OutcomeEvidenceError, match="OUTCOME_EVIDENCE_IDENTITY_MISMATCH"):
        OutcomeEvidenceManifest.from_dict(_manifest([_row(), other]))
    other = _row(outcome_unit="POINTS")
    other["replay_digest"] = row_replay_digest({k: v for k, v in other.items() if k != "replay_digest"})
    with pytest.raises(OutcomeEvidenceError, match="OUTCOME_CONTRACT_MISMATCH"):
        OutcomeEvidenceManifest.from_dict(_manifest([_row(), other]))


@pytest.mark.parametrize("value", [math.nan, math.inf, {1: "invalid"}, object()])
def test_non_finite_and_invalid_nested_canonical_values(value):
    row = _row()
    if isinstance(value, float):
        row["outcome"] = value
    else:
        row["features"] = {"bad": value}
    row["replay_digest"] = "0" * 64
    with pytest.raises(OutcomeEvidenceError, match="OUTCOME_EVIDENCE_SCHEMA_INVALID"):
        OutcomeEvidenceManifest.from_dict(_manifest([row]))


def test_validate_and_inspect_are_non_mutating_and_no_latest_api(tmp_path):
    source = _write(tmp_path / "source.json", _manifest())
    before = set(tmp_path.rglob("*"))
    result = validate(source)
    assert result["mutation_occurred"] is False and set(tmp_path.rglob("*")) == before
    state = inspect(tmp_path)
    assert state["mutation_occurred"] is False and state["record_count"] == 0
    assert not hasattr(OutcomeEvidenceRepository(tmp_path), "latest")


def test_import_idempotency_exact_lookup_and_raw_pr175_handoff(tmp_path):
    source = _write(tmp_path / "source.json", _manifest())
    first = import_evidence(source, tmp_path); second = import_evidence(source, tmp_path)
    assert first["mutation_occurred"] and not second["mutation_occurred"]
    assert first["evidence_uuid"] == second["evidence_uuid"]
    exact = inspect(tmp_path, first["evidence_uuid"])
    assert exact["record_count"] == 1
    record = OutcomeEvidenceRepository(tmp_path).load(first["evidence_uuid"])
    assert record["manifest"]["evidence_rows"][0]["features"] == {"trend": "up"}
    with pytest.raises(OutcomeEvidenceError, match="OUTCOME_EVIDENCE_FILE_MISSING"):
        OutcomeEvidenceRepository(tmp_path).load("33333333-3333-5333-8333-333333333333")


def test_same_identity_different_bytes_collision_and_corruption(tmp_path):
    source = _write(tmp_path / "source.json", _manifest())
    result = import_evidence(source, tmp_path)
    repository = OutcomeEvidenceRepository(tmp_path)
    record = repository.load(result["evidence_uuid"])
    altered = json.loads(json.dumps(record)); altered["source_digest"] = "f" * 64
    with pytest.raises(OutcomeEvidenceError, match="AMBIGUOUS_EVIDENCE_IDENTITY"):
        repository.save(altered)
    repository.path_for(result["evidence_uuid"]).write_text("{}", encoding="utf-8")
    with pytest.raises(OutcomeEvidenceError, match="EVIDENCE_REPOSITORY_CORRUPT"):
        repository.load(result["evidence_uuid"])


def test_exact_pr173_construction_source_replay_and_duplicate(tmp_path):
    source = _write(tmp_path / "source.json", _manifest())
    imported = import_evidence(source, tmp_path)
    first = construct_pr173(tmp_path, imported["evidence_uuid"])
    second = construct_pr173(tmp_path, imported["evidence_uuid"])
    assert UUID(first["attribution_uuid"])
    assert first["source_digest"] == imported["source_digest"]
    assert first["replay_digest"] == imported["replay_digest"]
    assert first["mutation_occurred"] and second["duplicate_replay"]


def test_interrupted_import_retry_safe(monkeypatch, tmp_path):
    source = _write(tmp_path / "source.json", _manifest())
    import learning.outcome_evidence.repository as module
    real_link = module.os.link
    monkeypatch.setattr(module.os, "link", lambda *_: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError):
        import_evidence(source, tmp_path)
    assert not list((tmp_path / "outcome_evidence").glob("evidence_*.json"))
    monkeypatch.setattr(module.os, "link", real_link)
    assert import_evidence(source, tmp_path)["mutation_occurred"]


def test_acquisition_has_no_trading_side_effect_imports():
    import learning.outcome_evidence.operator_acquisition as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("runtime.", "strategy.", "risk.", "writer.", "executor.", "OrderSend"):
        assert forbidden not in source
