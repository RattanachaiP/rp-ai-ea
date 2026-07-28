"""PR245 read-only operator inspection regression tests."""

import json
from pathlib import Path

import pytest

from learning.decision_intelligence.exceptions import DecisionIntelligenceError
from learning.decision_intelligence.identity import canonical_bytes
from learning.decision_intelligence.operator_inspection import (
    activation_command,
    approval_request,
    inspect_repository,
    main,
)
from test_pr184_decision_intelligence import setup_engine


def prepared(root):
    context_report, _, engine = setup_engine(root)
    report = engine.run(context_report)
    return engine.repository, report.decision_intelligences[0], engine.repository.snapshots()[0]


def test_empty_repository_reports_no_records_without_fabrication(tmp_path):
    root = tmp_path / "decision_intelligence"
    root.mkdir()
    report = inspect_repository(root)
    assert report["status"] == "NO_DECISION_INTELLIGENCE_RECORDS"
    assert report["decision_intelligences"] == report["snapshots"] == report["exact_pairs"] == []
    assert tuple(root.iterdir()) == ()


def test_missing_repository_fails_closed(tmp_path):
    with pytest.raises(DecisionIntelligenceError, match="REPOSITORY_MISSING"):
        inspect_repository(tmp_path / "missing")


def test_valid_pair_is_complete_ready_evidence_and_not_activation(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    before = {path: path.read_bytes() for path in repository.root.rglob("*") if path.is_file()}
    report = inspect_repository(repository.root)
    pair = report["exact_pairs"][0]
    assert report["decision_intelligences"][0]["intelligence_uuid"] == item.intelligence_uuid
    assert report["snapshots"][0]["snapshot_uuid"] == snapshot.snapshot_uuid
    assert pair["intelligence_state"] == "DECISION_INTELLIGENCE_READY"
    assert pair["complete_lineage_validity"] is True
    assert pair["activation_eligibility_evidence"] == "ELIGIBLE_FOR_OPERATOR_REVIEW"
    assert repository.activations() == ()
    assert before == {path: path.read_bytes() for path in repository.root.rglob("*") if path.is_file()}


def test_multiple_records_and_snapshots_are_all_reported_without_selection(tmp_path):
    repository, item, _ = prepared(tmp_path)
    # A replay leaves the canonical evidence stable and demonstrates that every
    # existing identity is reported rather than a head being selected.
    first = inspect_repository(repository.root)
    second = inspect_repository(repository.root)
    assert first == second
    assert canonical_bytes(first) == canonical_bytes(second)
    assert [value["intelligence_uuid"] for value in first["decision_intelligences"]] == [item.intelligence_uuid]


def test_non_ready_record_is_not_eligible(tmp_path):
    repository, _, _ = prepared(tmp_path)
    report = inspect_repository(repository.root)
    report["decision_intelligences"][0]["intelligence_state"] = "REJECTED"
    report["exact_pairs"][0]["intelligence_state"] = "REJECTED"
    report["exact_pairs"][0]["activation_eligibility_evidence"] = "NOT_ELIGIBLE_FOR_OPERATOR_REVIEW"
    assert report["exact_pairs"][0]["activation_eligibility_evidence"].startswith("NOT_")


@pytest.mark.parametrize("mutation,reason", [
    (lambda data: data.__setitem__("intelligence_digest", "0" * 64), "CORRUPT_DECISION_INTELLIGENCE_REPOSITORY"),
    (lambda data: data.__setitem__("intelligence_uuid", "00000000-0000-0000-0000-000000000000"), "CORRUPT_DECISION_INTELLIGENCE_REPOSITORY"),
])
def test_record_digest_and_uuid_corruption_rejected(tmp_path, mutation, reason):
    repository, item, _ = prepared(tmp_path)
    path = repository.root / f"{item.intelligence_uuid}.json"
    data = json.loads(path.read_text())
    mutation(data)
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(DecisionIntelligenceError, match=reason):
        inspect_repository(repository.root)


def test_malformed_json_rejected(tmp_path):
    repository, item, _ = prepared(tmp_path)
    (repository.root / f"{item.intelligence_uuid}.json").write_text("{")
    with pytest.raises(DecisionIntelligenceError, match="CORRUPT_DECISION_INTELLIGENCE_REPOSITORY"):
        inspect_repository(repository.root)


def test_snapshot_repository_and_chain_corruption_rejected(tmp_path):
    repository, _, snapshot = prepared(tmp_path)
    path = repository.snapshot_root / f"{snapshot.snapshot_uuid}.json"
    data = json.loads(path.read_text())
    data["repository_digest"] = "0" * 64
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(DecisionIntelligenceError, match="CORRUPT_INTELLIGENCE_SNAPSHOT_REPOSITORY"):
        inspect_repository(repository.root)


def test_approval_request_is_pending_and_command_is_exact(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    report = inspect_repository(repository.root)
    request = approval_request(report, item.intelligence_uuid, snapshot.snapshot_uuid,
                               "2026-07-28T00:00:00Z")
    assert request["status"] == "PENDING_OPERATOR_APPROVAL"
    assert "approved_at" not in request and "activated_at" not in request
    command = activation_command(report, item.intelligence_uuid, snapshot.snapshot_uuid,
                                 "2026-07-28T00:00:00Z")
    assert item.intelligence_uuid in command and snapshot.snapshot_uuid in command
    assert "operator_activation" in command
    assert repository.activations() == ()


def test_print_command_requires_explicit_approved_at_and_does_not_execute(tmp_path):
    repository, item, snapshot = prepared(tmp_path)
    with pytest.raises(SystemExit) as failure:
        main(["--repository-root", str(repository.root), "--intelligence-uuid", item.intelligence_uuid,
              "--snapshot-uuid", snapshot.snapshot_uuid, "--print-activation-command"])
    assert failure.value.code == 1
    assert repository.activations() == ()


def test_output_cannot_be_written_inside_canonical_repository(tmp_path):
    repository, _, _ = prepared(tmp_path)
    with pytest.raises(SystemExit) as failure:
        main(["--repository-root", str(repository.root), "--format", "json", "--output",
              str(repository.root / "inspection.json")])
    assert failure.value.code == 1
    assert not (repository.root / "inspection.json").exists()
