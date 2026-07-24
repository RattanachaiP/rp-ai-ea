from dataclasses import replace
import pytest
from learning.applicability import *

def candidate(identifier="a", **changes):
    return replace(GatewayKnowledge(identifier, "family/xauusd", 4, "1.0", "1.0", ("V27",), ("FEATURE_A",), ("XAUUSD",), ("LONDON",), ("M15",), ("TREND",), ("LIVE",), 5, .8), **changes)
def snapshot(records):
    body={"snapshot_uuid":"gateway-1", "schema_version":"1.0", "configuration_version":"1.0", "records":[__import__('dataclasses').asdict(x) for x in records]}
    return GatewaySnapshot("gateway-1", canonical_digest(body), "1.0", "1.0", tuple(records))
def context(**changes):
    value=RuntimeContext("XAUUSD","M15","LONDON","TREND","NORMAL","UP","LIVE","V27",("FEATURE_A",))
    return replace(value, **changes)

def test_matches_all_context_factors_and_returns_a_deterministic_projection():
    report=KnowledgeApplicabilityEngine().evaluate(snapshot((candidate("z"), candidate("a", semantic_identity="family/second", priority=6))), context())
    assert [x.knowledge_uuid for x in report.applicable] == ["a", "z"]
    assert report.applicable[0].matching_factors == ("SYMBOL_MATCH","SESSION_MATCH","TIMEFRAME_MATCH","REGIME_MATCH","EXECUTION_PROFILE_MATCH","RUNTIME_VERSION_MATCH")
    assert report.applicable[0].applicability_score == 1.0 and report.confidence == .8

def test_rejects_context_and_compatibility_mismatches_with_reason_codes():
    records=(candidate("wrong-session", sessions=("ASIA",)), candidate("wrong-runtime", supported_runtime_versions=("V26",)), candidate("missing-feature", required_features=("B",)))
    report=KnowledgeApplicabilityEngine().evaluate(snapshot(records), context())
    assert report.applicable == ()
    assert dict(report.rejected)["wrong-session"] == ("SYMBOL_MATCH","SESSION_MISMATCH","TIMEFRAME_MATCH","REGIME_MATCH","EXECUTION_PROFILE_MATCH","SCHEMA_MATCH","CONFIGURATION_MATCH","RUNTIME_VERSION_MATCH","FEATURE_MATCH")
    assert "UNSUPPORTED_RUNTIME_VERSION" in dict(report.rejected)["wrong-runtime"]
    assert "FEATURE_MISMATCH" in dict(report.rejected)["missing-feature"]

def test_conflicts_select_one_semantic_identity_and_replay_is_stable():
    high=candidate("high", priority=9, confidence=.6); low=candidate("low", priority=2, confidence=.99)
    engine=KnowledgeApplicabilityEngine(); first=engine.evaluate(snapshot((low,high)), context()); second=engine.evaluate(snapshot((high,low)), context())
    assert [x.knowledge_uuid for x in first.applicable] == ["high"]
    assert "CONFLICT_SUPERSEDED" in dict(first.rejected)["low"]
    assert [x.knowledge_uuid for x in second.applicable] == ["high"] and engine.lookup("high") == second.applicable[0]

@pytest.mark.parametrize("mutate,code", [(lambda x: replace(x, snapshot_digest="0"*64),"DIGEST_MISMATCH"), (lambda x: snapshot((candidate("a"),candidate("a"))),"DUPLICATE_CANDIDATE")])
def test_fail_closed_for_digest_and_duplicate_candidates(mutate, code):
    with pytest.raises(ApplicabilityEvaluationError, match=code): KnowledgeApplicabilityEngine().evaluate(mutate(snapshot((candidate(),))), context())

def test_unknown_context_and_append_only_report_repository(tmp_path):
    with pytest.raises(ApplicabilityEvaluationError, match="UNKNOWN_SESSION"): KnowledgeApplicabilityEngine().evaluate(snapshot((candidate(),)), context(session="UNKNOWN"))
    repo=ApplicabilityReportRepository(tmp_path); report=KnowledgeApplicabilityEngine(report_repository=repo).evaluate(snapshot((candidate(),)), context())
    assert repo.append(report).exists()
