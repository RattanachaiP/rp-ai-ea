from dataclasses import replace
from pathlib import Path

import pytest

from runtime.knowledge_gateway import KnowledgeRuntimeSnapshot, RuntimeKnowledgeDescriptor
from runtime.knowledge_applicability import (
    ApplicabilityEvaluationError,
    ApplicabilityReport,
    KnowledgeApplicabilityEngine,
    RuntimeContext,
)
from runtime.applicability_storage import ApplicabilityReportRepository


def descriptor(identifier="a", *, semantic="family/xauusd", sequence=1, **metadata_changes):
    metadata = {
        "supported_runtime_versions": ("27.0.0",),
        "required_features": ("FEATURE_A",),
        "symbols": ("XAUUSD",),
        "sessions": ("LONDON",),
        "timeframes": ("M15",),
        "market_regimes": ("TREND",),
        "volatility_classes": ("NORMAL",),
        "trend_states": ("UP",),
        "execution_profiles": ("LIVE",),
        "priority": 5,
        "confidence": 0.8,
    }
    metadata.update(metadata_changes)
    return RuntimeKnowledgeDescriptor(
        knowledge_uuid=identifier,
        activation_uuid=f"activation-{identifier}",
        semantic_identity=semantic,
        sequence=sequence,
        schema_version="1.0.0",
        configuration_version="1.0.0",
        activated_at="2026-01-01T00:00:00Z",
        metadata=metadata,
    )


def snapshot(entries, *, digest="1" * 64, gateway="1.0.0", policy="1.0.0"):
    return KnowledgeRuntimeSnapshot(
        snapshot_digest=digest,
        registry_digest="2" * 64,
        gateway_contract_version=gateway,
        compatibility_policy_version=policy,
        supported_schema_majors=(1,),
        supported_configuration_majors=(1,),
        highest_registry_sequence=max((item.sequence for item in entries), default=0),
        source_event_count=len(entries),
        generated_at="2026-01-01T00:00:01Z",
        entries=tuple(entries),
        rejected={},
    )


def context(**changes):
    value = RuntimeContext("XAUUSD", "M15", "LONDON", "TREND", "NORMAL", "UP", "LIVE", "27.0.0", ("FEATURE_A",))
    return replace(value, **changes)


def test_consumes_pr158_snapshot_and_matches_all_runtime_dimensions():
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor(),)), context())
    assert [item.knowledge_uuid for item in report.applicable] == ["a"]
    assert report.applicable[0].specificity_score == 1.0
    assert "VOLATILITY_MATCH" in report.applicable[0].matching_factors
    assert "TREND_STATE_MATCH" in report.applicable[0].matching_factors
    assert report.confidence == 0.8


def test_wildcards_are_valid_but_less_specific_than_exact_matches():
    exact = descriptor("exact", sequence=1, priority=5)
    wildcard = descriptor(
        "wild", sequence=2, priority=5,
        symbols=("*",), sessions=("*",), timeframes=("*",), market_regimes=("*",),
        volatility_classes=("*",), trend_states=("*",), execution_profiles=("*",),
        supported_runtime_versions=("*",),
    )
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((wildcard, exact)), context())
    assert [item.knowledge_uuid for item in report.applicable] == ["exact"]
    assert "CONFLICT_SUPERSEDED" in dict(report.rejected)["wild"]


def test_mismatch_and_runtime_version_fail_closed_with_stable_codes():
    entries = (
        descriptor("vol", sequence=1, volatility_classes=("HIGH",)),
        descriptor("trend", sequence=2, trend_states=("DOWN",)),
        descriptor("version", sequence=3, supported_runtime_versions=("26.0.0",)),
    )
    rejected = dict(KnowledgeApplicabilityEngine().evaluate(snapshot(entries), context()).rejected)
    assert "VOLATILITY_MISMATCH" in rejected["vol"]
    assert "TREND_STATE_MISMATCH" in rejected["trend"]
    assert "UNSUPPORTED_RUNTIME_VERSION" in rejected["version"]


def test_engine_is_stateless_and_rejects_invalid_contract_versions():
    engine = KnowledgeApplicabilityEngine()
    assert not hasattr(engine, "_last")
    with pytest.raises(ApplicabilityEvaluationError, match="UNSUPPORTED_GATEWAY"):
        engine.evaluate(snapshot((), gateway="2.0.0"), context())
    with pytest.raises(ApplicabilityEvaluationError, match="UNSUPPORTED_COMPATIBILITY"):
        engine.evaluate(snapshot((), policy="2.0.0"), context())
    with pytest.raises(ValueError, match="INVALID_RUNTIME_VERSION"):
        context(runtime_version="V27")


def test_duplicate_sequence_and_candidate_uuid_are_rejected():
    with pytest.raises(ApplicabilityEvaluationError, match="DUPLICATE_APPLICABILITY_CANDIDATE"):
        KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor("a", sequence=1), descriptor("b", sequence=1, semantic="family/b"))), context())
    with pytest.raises(ApplicabilityEvaluationError, match="DUPLICATE_APPLICABILITY_CANDIDATE"):
        KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor("a", sequence=1), descriptor("a", sequence=2, semantic="family/b"))), context())


def test_report_rejects_forged_digest_and_uuid():
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor(),)), context())
    with pytest.raises(ValueError, match="DIGEST_MISMATCH"):
        replace(report, report_digest="0" * 64)
    with pytest.raises(ValueError, match="UUID_MISMATCH"):
        replace(report, report_uuid="forged")


def test_append_only_repository_is_idempotent_and_detects_collision(tmp_path):
    report = KnowledgeApplicabilityEngine().evaluate(snapshot((descriptor(),)), context())
    repository = ApplicabilityReportRepository(tmp_path)
    path = repository.append(report)
    assert repository.append(report) == path
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="APPEND_ONLY"):
        repository.append(report)
    assert not list(Path(tmp_path).rglob("*.tmp"))
