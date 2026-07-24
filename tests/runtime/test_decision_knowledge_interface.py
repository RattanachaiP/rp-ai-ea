"""PR160 regression coverage for the Decision Knowledge Interface."""
from dataclasses import FrozenInstanceError, replace
from math import nan
import pytest

from runtime.decision_knowledge_interface import (
    DecisionKnowledgeAccessError,
    DecisionKnowledgeInterface,
)
from runtime.knowledge_applicability import ApplicabilityReport, KnowledgeApplicabilityEngine
from tests.learning.test_knowledge_applicability import context, descriptor, snapshot


def report(identifier: str = "knowledge-a"):
    return KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor(identifier),)), context())


def test_read_contract_is_immutable_hides_metadata_and_retains_no_source_report():
    source = report()
    dki = DecisionKnowledgeInterface.load(source)
    item = dki.list_applicable()[0]
    assert item.applicability_score == 1.0
    assert not hasattr(item, "metadata")
    assert not hasattr(dki, "_report")
    with pytest.raises(FrozenInstanceError):
        item.priority = 99


def test_lookup_resolve_and_public_identity_access_are_deterministic():
    source = report("plain-non-rfc-identifier")
    with pytest.raises(DecisionKnowledgeAccessError, match="SNAPSHOT_REQUIRED"):
        DecisionKnowledgeInterface(source)
    dki = DecisionKnowledgeInterface.load(source)
    item = dki.list_applicable()[0]
    assert dki.lookup(item.knowledge_uuid) == item
    assert dki.resolve(item.semantic_identity) == item
    assert dki.list_applicable() == dki.list_applicable()
    assert dki.report_uuid() == source.report_uuid
    assert dki.report_digest() == source.report_digest
    assert dki.snapshot_digest() == source.snapshot_digest


def test_record_validation_rejects_nan_ranges_and_bad_provenance():
    valid = DecisionKnowledgeInterface.load(report()).list_applicable()[0]
    for changes in (
        {"applicability_score": nan},
        {"confidence": 2.0},
        {"priority": -1},
        {"registry_sequence": 0},
        {"snapshot_digest": "x" * 64},
    ):
        with pytest.raises(DecisionKnowledgeAccessError):
            replace(valid, **changes)


def test_rejects_missing_and_corrupted_reports_fail_closed():
    with pytest.raises(DecisionKnowledgeAccessError, match="MISSING"):
        DecisionKnowledgeInterface.load(None)
    valid = report()
    object.__setattr__(valid, "report_digest", "0" * 64)
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED"):
        DecisionKnowledgeInterface.load(valid)


def test_rejects_unsupported_explicit_report_contract_without_fallback():
    valid = report()
    object.__setattr__(valid, "report_contract_version", "2.0.0")
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED|UNSUPPORTED"):
        DecisionKnowledgeInterface.load(valid)
    valid = report()
    object.__delattr__(valid, "report_contract_version")
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED"):
        DecisionKnowledgeInterface.load(valid)


def test_rejects_duplicate_records_and_provenance_mismatch():
    valid = report()
    duplicate = ApplicabilityReport(
        valid.snapshot_digest,
        valid.context,
        valid.applicable + valid.applicable,
        valid.rejected,
        valid.confidence,
    )
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED"):
        DecisionKnowledgeInterface.load(duplicate)
    item = valid.applicable[0]
    corrupted_item = replace(item, snapshot_digest="0" * 64)
    with pytest.raises(ValueError, match="PROVENANCE"):
        ApplicabilityReport(
            valid.snapshot_digest,
            valid.context,
            (corrupted_item,),
            valid.rejected,
            valid.confidence,
        )


def test_strict_semver_rejects_numeric_prerelease_leading_zero():
    valid = report()
    object.__setattr__(valid, "report_contract_version", "1.0.0-01")
    with pytest.raises(DecisionKnowledgeAccessError, match="CORRUPTED|UNSUPPORTED"):
        DecisionKnowledgeInterface.load(valid)
