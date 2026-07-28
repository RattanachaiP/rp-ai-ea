"""PR267 production-readiness governance, integrity, lineage and authority tests."""
from dataclasses import replace

import pytest

from bridge.v28.campaign_statistics import aggregate_campaign_statistics
from bridge.v28.delivery_reliability_validator import validate_delivery_reliability
from bridge.v28.pipeline_validator import certification_identity
from bridge.v28.production_readiness_auditor import audit_production_readiness
from bridge.v28.production_readiness_candidate import create_production_readiness_candidate
from bridge.v28.production_readiness_lifecycle import transition_readiness
from bridge.v28.production_readiness_policy import create_production_readiness_policy
from bridge.v28.production_readiness_registry import create_production_readiness_registry
from bridge.v28.production_readiness_report import build_production_readiness_report
from bridge.v28.qualification_registry import create_registry
from bridge.v28.qualification_report import build_qualification_report
from bridge.v28.runtime_stability_monitor import monitor_runtime_stability
from bridge.v28.shadow_campaign_runner import run_shadow_campaign
from tests.test_v28_operational_qualification import campaign_fixture, policy, stamp


def evidence():
    qualification_policy = policy(required_consecutive_stable_campaigns=2, expiry_after_seconds=40)
    first = campaign_fixture(policy_value=qualification_policy, start=0)
    second = campaign_fixture(policy_value=qualification_policy, start=40, lineage=first.campaign_identity)
    third = campaign_fixture(policy_value=qualification_policy, start=80, lineage=second.campaign_identity)
    qualification_registry = create_registry(qualification_policy)
    for campaign, at in ((first, stamp(20)), (second, stamp(60)), (third, stamp(100))):
        qualification_registry = qualification_registry.append(campaign, appended_at=at)
    statistics = aggregate_campaign_statistics(qualification_registry)
    report = build_qualification_report(
        third, qualification_registry, statistics, monitor_runtime_stability(third),
        run_shadow_campaign(third), validate_delivery_reliability(third), assessed_at=stamp(100))
    readiness_policy = create_production_readiness_policy(
        minimum_runtime_duration_seconds=90, minimum_evidence_density_per_hour=1)
    candidate = create_production_readiness_candidate(
        qualification_registry=qualification_registry, qualification_report=report,
        campaign_statistics=statistics, policy=readiness_policy, architecture_version="V28",
        repository_commit="6857095", generation=1, previous_candidate_identity=None)
    registry = create_production_readiness_registry(readiness_policy).append(candidate)
    return candidate, registry


def test_policy_validation_is_immutable_and_identity_bound():
    governed = create_production_readiness_policy()
    with pytest.raises(Exception):
        governed.minimum_stable_campaigns = 9
    with pytest.raises(ValueError, match="CAMPAIGN_THRESHOLD"):
        create_production_readiness_policy(minimum_qualified_campaigns=1, minimum_stable_campaigns=2)
    with pytest.raises(ValueError, match="RATE"):
        create_production_readiness_policy(maximum_failure_rate=1.1)
    with pytest.raises(ValueError, match="IDENTITY"):
        replace(governed, policy_identity="forged")


def test_qualified_evidence_is_only_ready_for_human_review():
    candidate, registry = evidence()
    report = build_production_readiness_report(candidate, registry)
    assert report.status == "READY_FOR_HUMAN_REVIEW"
    assert not report.production_authorized and not report.deployment_performed
    assert report.to_json() == report.to_json()
    audit = audit_production_readiness(candidate, registry, report)
    assert audit.status == "PASS"


def test_lifecycle_is_forward_only_and_requires_human_lineage():
    candidate, registry = evidence()
    report = build_production_readiness_report(candidate, registry)
    with pytest.raises(ValueError, match="HUMAN"):
        transition_readiness(report, "UNDER_HUMAN_REVIEW", actor_identity="automation", reason="start", recorded_at=stamp(101))
    review = transition_readiness(report, "UNDER_HUMAN_REVIEW", actor_identity="HUMAN:reviewer", reason="review opened", recorded_at=stamp(101))
    approved = transition_readiness(review, "APPROVED_FOR_DEPLOYMENT", actor_identity="HUMAN:approver", reason="evidence accepted", recorded_at=stamp(102))
    assert approved.status == "APPROVED_FOR_DEPLOYMENT" and not approved.production_authorized
    assert approved.approval_history[1].previous_event_identity == approved.approval_history[0].event_identity
    with pytest.raises(ValueError, match="TRANSITION"):
        transition_readiness(approved, "UNDER_HUMAN_REVIEW", actor_identity="HUMAN:approver", reason="reverse", recorded_at=stamp(103))
    assert transition_readiness(approved, "SUPERSEDED", actor_identity="HUMAN:owner", reason="new submission", recorded_at=stamp(104)).status == "SUPERSEDED"


def test_registry_rejects_duplicates_broken_lineage_future_and_policy_mismatch():
    candidate, registry = evidence()
    with pytest.raises(ValueError, match="DUPLICATE"):
        registry.append(candidate)
    values = candidate.canonical_payload()
    values.update(generation=3, previous_candidate_identity=candidate.candidate_identity)
    future = create_production_readiness_candidate(**values)
    with pytest.raises(ValueError, match="FUTURE"):
        registry.append(future)
    values.update(generation=2, previous_candidate_identity="broken")
    broken = create_production_readiness_candidate(**values)
    with pytest.raises(ValueError, match="LINEAGE_BROKEN"):
        registry.append(broken)
    other_policy = create_production_readiness_policy(maximum_failure_rate=.1)
    values.update(previous_candidate_identity=candidate.candidate_identity, policy=other_policy)
    mismatch = create_production_readiness_candidate(**values)
    with pytest.raises(ValueError, match="POLICY_MISMATCH"):
        registry.append(mismatch)


def test_candidate_rejects_cross_report_architecture_and_repository_mismatch():
    candidate, _ = evidence()
    with pytest.raises(ValueError):
        replace(candidate.campaign_statistics, registry_identity="wrong",
                replay_identity=candidate.campaign_statistics.replay_identity)
    values = candidate.canonical_payload(); values["architecture_version"] = "V29"
    with pytest.raises(ValueError, match="VERSION_MISMATCH"):
        create_production_readiness_candidate(**values)
    values = candidate.canonical_payload(); values["repository_commit"] = "not-a-commit"
    with pytest.raises(ValueError, match="REPOSITORY"):
        create_production_readiness_candidate(**values)


def test_registry_snapshots_are_append_only():
    candidate, registry = evidence()
    old_identity, old_candidates = registry.registry_identity, registry.candidates
    values = candidate.canonical_payload()
    values.update(generation=2, previous_candidate_identity=candidate.candidate_identity,
                  repository_commit="abcdef1")
    second = create_production_readiness_candidate(**values)
    new_registry = registry.append(second)
    assert registry.registry_identity == old_identity and registry.candidates == old_candidates
    assert new_registry.previous_registry_identity == old_identity and new_registry.generation == 2
    with pytest.raises(ValueError):
        replace(new_registry, candidates=tuple(reversed(new_registry.candidates)),
                registry_identity=certification_identity("V28_PRODUCTION_READINESS_REGISTRY", new_registry.canonical_payload()))
