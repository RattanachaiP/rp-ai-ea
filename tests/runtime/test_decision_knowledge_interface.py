"""PR160 regression coverage for the Decision Knowledge Interface."""
import pytest

from runtime.decision_knowledge_interface import (
    DecisionKnowledgeAccessError, DecisionKnowledgeInterface, RuntimeQuery,
)
from runtime.knowledge_applicability import ApplicabilityReport, KnowledgeApplicabilityEngine
from tests.learning.test_knowledge_applicability import context, descriptor, snapshot


def report():
    # UUIDs are required by the DKI contract, unlike PR159's permissive test IDs.
    item = descriptor("63e5d9f5-0fd4-4d27-ae04-26486c6cbb61")
    return KnowledgeApplicabilityEngine().evaluate(snapshot((item,)), context())


def test_read_contract_is_immutable_and_hides_applicability_metadata():
    dki = DecisionKnowledgeInterface.load(report())
    item = dki.get_applicable()[0]
    assert item.applicability_score == 1.0
    assert not hasattr(item, "metadata")
    with pytest.raises(Exception):
        item.priority = 99


def test_lookup_resolve_and_digest_queries_are_deterministic():
    dki = DecisionKnowledgeInterface(report())
    item = dki.get_applicable()[0]
    query = RuntimeQuery(report_uuid=dki._report.report_uuid)
    assert dki.lookup(item.knowledge_uuid, query) == item
    assert dki.resolve(item.semantic_identity, query) == item
    assert dki.get_by_semantic_identity(item.semantic_identity) == item
    assert dki.list_applicable() == dki.get_applicable() == dki.get_applicable()
    assert dki.report_digest(query) == dki._report.report_digest
    assert dki.snapshot_digest(query) == dki._report.snapshot_digest
    assert set(dki.__dict__) == {"_report"}


def test_rejects_missing_invalid_and_corrupted_reports_fail_closed():
    with pytest.raises(DecisionKnowledgeAccessError, match="MISSING"):
        DecisionKnowledgeInterface.load(None)
    valid = report()
    object.__setattr__(valid, "report_uuid", "not-a-uuid")
    with pytest.raises(DecisionKnowledgeAccessError, match="INVALID_REPORT_UUID"):
        DecisionKnowledgeInterface.load(valid)
    valid = report()
    object.__setattr__(valid, "report_digest", "0" * 64)
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED"):
        DecisionKnowledgeInterface.load(valid)


def test_rejects_contract_version_and_wrong_report_selector():
    dki = DecisionKnowledgeInterface(report())
    with pytest.raises(DecisionKnowledgeAccessError, match="UNSUPPORTED"):
        RuntimeQuery(contract_version="2.0.0")
    with pytest.raises(DecisionKnowledgeAccessError, match="MISSING"):
        dki.get_applicable(RuntimeQuery(report_uuid="00000000-0000-0000-0000-000000000000"))


def test_rejects_unknown_report_version_and_duplicate_lookup_records():
    valid = report()
    object.__setattr__(valid, "report_version", "2.0.0")
    with pytest.raises(DecisionKnowledgeAccessError, match="UNKNOWN"):
        DecisionKnowledgeInterface.load(valid)

    valid = report()
    duplicate = ApplicabilityReport(valid.snapshot_digest, valid.context,
                                    valid.applicable + valid.applicable, valid.rejected,
                                    valid.confidence)
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED"):
        DecisionKnowledgeInterface.load(duplicate)
